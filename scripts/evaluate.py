#!/usr/bin/env python
import argparse
import asyncio
import json
from pathlib import Path

from medal import load_dotenv_if_present, require_env
from medal.clients import make_openai_async_client, bounded_json_chat_completion


EVAL_PROMPT = """
You are a clinical research expert with knowledge of systematic reviews, RCTs, and observational studies.
Task: Given a clinical question, return a JSON with keys question, answer, evidence-quality, discrepancy, notes.
Allowed values:
- answer: Yes | No | No Evidence
- evidence-quality: High | Moderate | Low | Very Low | Missing
- discrepancy: Yes | No | Missing
""".strip()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--max-concurrent", type=int, default=5)
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")
    client = make_openai_async_client(api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    records = []
    with open(args.input_jsonl, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                item = json.loads(line)
                records.append((str(i), item))
            except Exception:
                pass

    async def evaluate_one(idx: str, item: dict):
        q = item["question"]
        prompt = f"{EVAL_PROMPT}\n\nQuestion:\n\"\"\"{q}\"\"\""
        try:
            content = await bounded_json_chat_completion(client, args.model, prompt, semaphore, temperature=0.2)
            resp = json.loads(content)
        except Exception as e:
            resp = {
                "question": q,
                "answer": "ERROR",
                "evidence-quality": "ERROR",
                "discrepancy": "ERROR",
                "notes": str(e),
            }
        return {
            idx: {
                "doi": item.get("doi", ""),
                "question": q,
                "model_answer": resp.get("answer", ""),
                "model_evidence-quality": resp.get("evidence-quality", ""),
                "model_discrepancy": resp.get("discrepancy", ""),
                "model_notes": resp.get("notes", ""),
                "ground_truth_answer": item.get("answer", ""),
                "ground_truth_evidence-quality": item.get("evidence-quality", ""),
                "ground_truth_discrepancy": item.get("discrepancy", ""),
            }
        }

    tasks = [evaluate_one(idx, item) for idx, item in records]
    out = {}
    for coro in asyncio.as_completed(tasks):
        out.update(await coro)

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as w:
        json.dump(out, w, indent=2)


if __name__ == "__main__":
    asyncio.run(main())



