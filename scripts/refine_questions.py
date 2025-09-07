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

from medal import load_dotenv_if_present, require_env
from medal.clients import make_openai_async_client, bounded_json_chat_completion


REFINE_PROMPT = (
    """
You are an expert clinical research assistant and methodologist.

Given a proposed QA item with fields {question, answer, evidence-quality, discrepancy, notes}, refine it to be:
- faithful to the abstract (do not invent facts),
- unambiguous and concise,
- consistent with allowed value sets.

Allowed values:
- answer: Yes | No | No Evidence
- evidence-quality: High | Moderate | Low | Very Low | Missing
- discrepancy: Yes | No | Missing

Return a single JSON object with keys:
{ "question", "answer", "evidence-quality", "discrepancy", "notes" }

Notes requirement:
- In "notes", briefly cite the supporting evidence: provide a short direct quote when possible; if unavailable, provide a concise paraphrase clearly labeled as paraphrase. Keep under 35 words and avoid hallucinations.
"""
).strip()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Refine generated QA items using a specified model")
    parser.add_argument("--input-jsonl", required=True, help="Input JSONL of QA items {doi, question, answer, evidence-quality, discrepancy, notes}")
    parser.add_argument("--out-jsonl", required=True, help="Output JSONL of refined QA items (same schema)")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--max-concurrent", type=int, default=8)
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")
    client = make_openai_async_client(api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    records = []
    with open(args.input_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                records.append(item)
            except Exception:
                pass

    async def refine_one(item: dict):
        qa = {
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "evidence-quality": item.get("evidence-quality", ""),
            "discrepancy": item.get("discrepancy", ""),
            "notes": item.get("notes", ""),
        }
        prompt = f"{REFINE_PROMPT}\n\nProposed QA item:\n```json\n{json.dumps(qa, ensure_ascii=False)}\n```"
        try:
            use_temp = None if str(args.model).startswith("gpt-5") else 0.1
            content = await bounded_json_chat_completion(
                client,
                args.model,
                prompt,
                semaphore,
                temperature=use_temp,
                reasoning_effort="medium" if str(args.model).startswith("gpt-5") else None,
            )
            refined = json.loads(content)
        except Exception as e:
            refined = qa
            refined["notes"] = (refined.get("notes", "") + f" | refine_error: {e}").strip()
        # keep original doi if present
        refined_record = {
            "doi": item.get("doi", ""),
            "question": refined.get("question", qa["question"]),
            "answer": refined.get("answer", qa["answer"]),
            "evidence-quality": refined.get("evidence-quality", qa["evidence-quality"]),
            "discrepancy": refined.get("discrepancy", qa["discrepancy"]),
            "notes": refined.get("notes", qa["notes"]),
        }
        return refined_record

    tasks = [refine_one(item) for item in records]
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as w:
        for coro in asyncio.as_completed(tasks):
            rec = await coro
            if rec:
                w.write(json.dumps(rec) + "\n")


if __name__ == "__main__":
    asyncio.run(main())


