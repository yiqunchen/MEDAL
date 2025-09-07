#!/usr/bin/env python
import sys
from pathlib import Path as _P
ROOT_DIR = _P(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import argparse
import json
from pathlib import Path
from typing import Optional

from medal import load_dotenv_if_present


PROMPT_TEMPLATE = (
    """
You are a clinical research expert with comprehensive knowledge of systematic reviews, randomized controlled trials (RCTs), and observational studies. Your task is to assess a clinical question and return a structured judgment using evidence-based reasoning.

For the given question, provide:

1. A binary answer: "Yes", "No", or "No Evidence", based on whether the available evidence supports the claim.
2. The overall quality of evidence: choose one from "High", "Moderate", "Low", "Very Low", or "Missing", using standard evidence grading principles (e.g., GRADE).
3. Whether there is a discrepancy in findings across study types, such as a conflict between RCTs and observational studies: "Yes", "No", or "Missing".
4. A brief explanatory note that cites the supporting evidence: include a short direct quote from the evidence when possible; if no direct quote is available, provide a concise paraphrase clearly marked as paraphrase. Keep the note under 35 words and avoid hallucinations.

Here is the clinical question:

\"\"\"{question}\"\"\"

Return your response in the following JSON format:

{{
  "question": "{question}",
  "answer": "Yes" or "No" or "No Evidence",
  "evidence-quality": "High" or "Moderate" or "Low" or "Very Low" or "Missing",
  "discrepancy": "Yes" or "No" or "Missing",
  "notes": "Brief explanation if needed"
}}
"""
).strip()


def safe_id(raw: Optional[str], fallback: str) -> str:
    if raw is None or not str(raw).strip():
        return fallback
    return str(raw).strip().replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare OpenAI Batch JSONL for chat completions")
    parser.add_argument("--input-jsonl", required=True, help="Path to input QAPair JSONL")
    parser.add_argument("--out-jsonl", required=True, help="Path to write batch input JSONL")
    parser.add_argument("--model", default="gpt-4o-mini", help="Target model (e.g., gpt-4o-mini, gpt-5)")
    parser.add_argument("--response-format-json", action="store_true", help="Request JSON response_format for stricter parsing")
    args = parser.parse_args()

    load_dotenv_if_present()

    in_path = Path(args.input_jsonl)
    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    num = 0
    with in_path.open("r", encoding="utf-8") as r, out_path.open("w", encoding="utf-8") as w:
        for line in r:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue

            qid = record.get("id")
            doi = record.get("doi")
            question = record.get("question", "").strip()
            if not question:
                continue

            num += 1
            identifier = safe_id(qid, safe_id(doi, f"row-{num}"))
            custom_id = f"qid:{identifier}"

            prompt = PROMPT_TEMPLATE.format(question=question)

            if str(args.model).startswith("gpt-5"):
                # Use Chat Completions for GPT-5 in batch; omit temperature/reasoning
                body = {
                    "model": args.model,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if args.response_format_json:
                    body["response_format"] = {"type": "json_object"}
                batch_line = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": body,
                }
            else:
                body = {
                    "model": args.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                }
                if args.response_format_json:
                    body["response_format"] = {"type": "json_object"}
                batch_line = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": body,
                }

            w.write(json.dumps(batch_line) + "\n")


if __name__ == "__main__":
    main()


