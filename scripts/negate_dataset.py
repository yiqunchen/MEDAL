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

from medal import load_dotenv_if_present, require_env
from medal.clients import make_openai_async_client, bounded_json_chat_completion


def build_negation_prompt(entry: dict) -> str:
    return f"""
You are a clinical research expert.
Negate the 'question' and 'answer' fields following rules:
- Prefer antonymic verb flips (increase/decrease, improve/worsen, promote/inhibit) over 'does not ...'.
- If negation is not logically derivable, set question to "Not applicable" and answer to "Not applicable".
- If original answer is "No Evidence", leave it as "No Evidence".

Return ONLY a JSON object with keys: doi, question, answer, original_question, original_answer, evidence-quality, discrepancy.

Original:
{{
  "doi": "{entry.get('doi','')}",
  "question": "{entry.get('question','').replace('"','\\"')}",
  "answer": "{entry.get('answer','')}",
  "evidence-quality": "{entry.get('evidence-quality','')}",
  "discrepancy": "{entry.get('discrepancy','')}"
}}
""".strip()


def negation_valid(original: str, negated: str) -> bool:
    if original == "Yes" and negated == "No":
        return True
    if original == "No" and negated == "Yes":
        return True
    if original == "No Evidence" and negated == "No Evidence":
        return True
    return False


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", required=True)
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max-concurrent", type=int, default=5)
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")
    client = make_openai_async_client(api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    inputs = []
    with open(args.input_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            try:
                inputs.append(json.loads(line))
            except Exception:
                pass

    async def process_one(entry: dict):
        prompt = build_negation_prompt(entry)
        try:
            use_temp = None if str(args.model).startswith("gpt-5") else 0.2
            content = await bounded_json_chat_completion(
                client,
                args.model,
                prompt,
                semaphore,
                temperature=use_temp,
                reasoning_effort="medium" if str(args.model).startswith("gpt-5") else None,
            )
            data = json.loads(content)
            data["negation-valid"] = negation_valid(entry.get("answer", ""), data.get("answer", ""))
            return data
        except Exception:
            return None

    tasks = [process_one(item) for item in inputs]
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as w:
        for coro in asyncio.as_completed(tasks):
            item = await coro
            if item:
                w.write(json.dumps(item) + "\n")


if __name__ == "__main__":
    asyncio.run(main())



