#!/usr/bin/env python
import sys
from pathlib import Path as _P
ROOT_DIR = _P(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict
from tqdm import tqdm

from medal import load_dotenv_if_present, require_env
from medal.clients import make_openai_async_client, bounded_json_chat_completion


PROMPT_TEMPLATE = """
You are an expert clinical research assistant and medical researcher.

Given the following abstract, generate a structured set of 2-4 challenging questions that assess intrinsic clinical understanding.
Each question should be answerable as Yes/No/No Evidence and include optional evidence quality and discrepancy fields.

Return a JSON list of 2 to 4 entries, each with keys: question, answer, evidence-quality, discrepancy, notes.

Abstract:\n"""


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-pkl", required=False, help="Path to pickle of {doi: {abstract, publication_year}}")
    parser.add_argument("--input-jsonl", required=False, help="Path to JSONL with {doi, abstract, publication_year?}")
    parser.add_argument("--out-jsonl", required=True, help="Path to write questions JSONL")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--max-concurrent", type=int, default=8)
    parser.add_argument("--errors-jsonl", required=False, help="Optional path to write per-item errors")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit of abstracts to process")
    parser.add_argument("--resume", action="store_true", help="Resume from existing outputs to avoid re-generating already completed DOIs")
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")

    # Load abstracts from either PKL or JSONL
    pubmed_abstract_data: Dict[str, dict] = {}
    if args.input_pkl:
        import pickle
        with open(args.input_pkl, "rb") as f:
            pubmed_abstract_data = pickle.load(f)
    elif args.input_jsonl:
        from typing import Any
        with open(args.input_jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                doi = item.get("doi")
                abstract = item.get("abstract", "")
                pub_yr = item.get("publication_year")
                if doi and abstract:
                    pubmed_abstract_data[str(doi)] = {"abstract": abstract, "publication_year": pub_yr}
    else:
        raise SystemExit("Provide either --input-pkl or --input-jsonl")

    client = make_openai_async_client(api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    async def process_one(doi: str, abstract_data: dict):
        abstract_text = abstract_data.get("abstract", "")
        if not abstract_text:
            return ("skip", doi, "missing_abstract")
        prompt = (
            PROMPT_TEMPLATE
            + "\n\n\"\"\"\n"
            + abstract_text
            + "\n\"\"\"\n"
        )
        try:
            # For gpt-5, avoid temperature and set medium reasoning effort
            use_temp = None if str(args.model).startswith("gpt-5") else 0.2
            content = await bounded_json_chat_completion(
                client,
                args.model,
                prompt,
                semaphore,
                temperature=use_temp,
                reasoning_effort="medium" if str(args.model).startswith("gpt-5") else None,
            )
            parsed = json.loads(content)
            return ("ok", doi, parsed)
        except Exception as e:
            return ("err", doi, str(e))

    items = list(pubmed_abstract_data.items())
    if args.limit and args.limit > 0:
        items = items[: args.limit]
    # Build skip set from existing outputs if resuming
    skip_dois = set()
    out_path = Path(args.out_jsonl)
    if args.resume and out_path.exists():
        try:
            with out_path.open("r", encoding="utf-8") as rf:
                for line in rf:
                    try:
                        rec = json.loads(line)
                        d = rec.get("doi")
                        if d:
                            skip_dois.add(str(d))
                    except Exception:
                        pass
        except Exception:
            pass
    if skip_dois:
        items = [(d, v) for (d, v) in items if str(d) not in skip_dois]
        print(f"Resuming: skipping {len(skip_dois)} DOIs already present in {out_path}")

    tasks = [process_one(doi, data) for doi, data in items]
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    err_writer = None
    if args.errors_jsonl:
        err_path = Path(args.errors_jsonl)
        err_path.parent.mkdir(parents=True, exist_ok=True)
        err_writer = err_path.open("w", encoding="utf-8")

    ok_count = 0
    skip_count = 0
    err_count = 0

    write_mode = "a" if args.resume and out_path.exists() else "w"
    with out_path.open(write_mode, encoding="utf-8") as w:
        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Generating"):
            tag, doi, payload = await coro
            if tag == "skip":
                skip_count += 1
                if err_writer:
                    err_writer.write(json.dumps({"doi": doi, "error": payload}) + "\n")
                continue
            if tag == "err":
                err_count += 1
                if err_writer:
                    err_writer.write(json.dumps({"doi": doi, "error": payload}) + "\n")
                continue
            # ok path
            qa_list = payload
            ok_count += 1
            if isinstance(qa_list, dict) and "question" in qa_list:
                qa_items = [qa_list]
            elif isinstance(qa_list, list):
                qa_items = qa_list
            else:
                # unexpected shape
                if err_writer:
                    err_writer.write(json.dumps({"doi": doi, "error": "invalid_shape"}) + "\n")
                continue
            for qa in qa_items:
                qa_record = {
                    "doi": doi,
                    "question": qa.get("question", ""),
                    "answer": qa.get("answer", ""),
                    "evidence-quality": qa.get("evidence-quality", "Missing"),
                    "discrepancy": qa.get("discrepancy", "Missing"),
                    "notes": qa.get("notes", ""),
                }
                w.write(json.dumps(qa_record) + "\n")

    if err_writer:
        err_writer.close()
    print(f"Done. ok={ok_count} err={err_count} skip={skip_count}")


if __name__ == "__main__":
    asyncio.run(main())



