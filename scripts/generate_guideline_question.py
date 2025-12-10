#!/usr/bin/env python
"""Generate guideline QA pairs from guideline text slices."""

import argparse
import asyncio
import csv
import json
import os
import pickle
import random
from pathlib import Path
from typing import Dict, List

import tqdm
from openai import AsyncOpenAI

from medal import load_dotenv_if_present, require_env

random.seed(2025)


def load_guideline_jsonl(file_path: Path) -> Dict[str, str]:
    """Load guideline text keyed by text-guideline (if present) plus index."""
    data: Dict[str, str] = {}
    with file_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            item = json.loads(line)
            text_id = item.get("text-guideline", f"guideline_{idx}")
            data[f"{text_id}_{idx}"] = item.get("text", "")
    return data


def slice_text(text: str, max_chars: int = 2000) -> List[str]:
    slices: List[str] = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            slices.append(current.strip())
            current = para + "\n\n"
    if current.strip():
        slices.append(current.strip())
    return slices


async def get_response_async(client: AsyncOpenAI, prompt: str, model: str, semaphore: asyncio.Semaphore) -> str:
    async with semaphore:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return completion.choices[0].message.content


async def process_guideline_slice(
    guideline_id: str,
    slice_id: str,
    slice_text_value: str,
    client: AsyncOpenAI,
    model: str,
    semaphore: asyncio.Semaphore,
) -> List[dict]:
    prompt = f"""
You are an expert clinical research assistant.

Given the following text from a guideline, generate **0 or 1 challenging clinical Yes/No/No evidence questions**.
- The question must be **specific and clinically actionable**, ideally involving a population, an intervention (or exposure), and an outcome (PICO style).
- The question must be direct clinical knowledge, **answerable without external context**, purely based on the text.
- Do **not** create questions about whether the guideline itself recommends, updates, or discusses a topic. Only ask questions that can be understood as standalone clinical facts.
- If there is insufficient content to form a **high-quality** question, return an **empty JSON array []**.

---
Here are examples to guide your style:

[
  {{
    "question": "In adults with chronic heart failure, does exercise therapy improve quality of life?",
    "answer": "Yes",
    "category": "heart failure",
    "supporting_snippet": "The text reports improved quality of life scores with exercise therapy."
  }},
  {{
    "question": "For women with urinary incontinence, does pelvic floor muscle training reduce episodes of incontinence?",
    "answer": "Yes",
    "category": "urinary incontinence",
    "supporting_snippet": "The text states fewer episodes of incontinence with pelvic floor exercises."
  }},
  {{
    "question": "In patients without cardiovascular risk factors, does daily aspirin reduce the incidence of major cardiovascular events?",
    "answer": "No",
    "category": "cardiovascular prevention",
    "supporting_snippet": "The text states aspirin does not reduce events in low-risk individuals."
  }}
]

---
Now, based on the following guideline text, generate a similar question.

Return strictly as a JSON array of objects like above.

Text:
\"\"\"
{slice_text_value}
\"\"\"
"""
    try:
        result = await get_response_async(client, prompt, model, semaphore)
        content = result.strip()
        if content.startswith("{"):
            print(f"Info: slice {slice_id} returned a single object, wrapping in list.")
            content = f"[{content}]"
        elif not content.startswith("["):
            print(f"Warning: slice {slice_id} did not return JSON array/object, got: {content[:80]}")
            return []
        qa_list = json.loads(content)
        if qa_list:
            print(f"Slice {slice_id} generated {len(qa_list)} QA.")
        else:
            print(f"Slice {slice_id} returned empty array [] (no relevant question).")
        return qa_list
    except Exception as e:
        print(f"Error parsing JSON for slice {slice_id}: {e}")
        return []


def save_partial_results(results: dict, output_csv_path: Path, output_pkl_path: Path) -> None:
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_pkl_path.parent.mkdir(parents=True, exist_ok=True)
    with output_pkl_path.open("wb") as f:
        pickle.dump(results, f)
    write_all_qa_to_csv(results, output_csv_path)
    print(f"[Checkpoint] Partial results saved to: {output_csv_path} and {output_pkl_path}")


async def process_all_guidelines(
    guideline_data: Dict[str, str],
    model: str,
    max_concurrent: int,
    api_key: str,
    checkpoint_every: int,
    checkpoint_csv: Path,
    checkpoint_pkl: Path,
    max_chars: int,
) -> dict:
    client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = {}
    slice_origin_map = {}
    for guideline_id, full_text in guideline_data.items():
        slices = slice_text(full_text, max_chars=max_chars)
        for i, slice_content in enumerate(slices):
            slice_id = f"{guideline_id}_slice_{i}"
            tasks[slice_id] = asyncio.create_task(
                process_guideline_slice(guideline_id, slice_id, slice_content, client, model, semaphore)
            )
            slice_origin_map[slice_id] = guideline_id

    results = {}
    pbar = tqdm.tqdm(total=len(tasks), desc="Processing slices")
    for idx, (slice_id, task) in enumerate(tasks.items(), start=1):
        try:
            result = await task
            if result is not None:
                results[slice_id] = {"guideline_id": slice_origin_map[slice_id], "qa_list": result}
        except Exception as e:
            print(f"Task error for {slice_id}: {e}")
        finally:
            pbar.update(1)

        if checkpoint_every and idx % checkpoint_every == 0:
            save_partial_results(results, checkpoint_csv, checkpoint_pkl)

    pbar.close()
    return results


def write_all_qa_to_csv(results: dict, output_csv_path: Path) -> None:
    rows = []
    for slice_id, slice_result in results.items():
        guideline_id = slice_result["guideline_id"]
        qa_list = slice_result["qa_list"]

        if isinstance(qa_list, dict) and "questions" in qa_list:
            qa_items = qa_list["questions"]
        elif isinstance(qa_list, list):
            qa_items = qa_list
        elif isinstance(qa_list, dict) and "question" in qa_list:
            qa_items = [qa_list]
        else:
            continue

        qa_items = [qa for qa in qa_items if isinstance(qa, dict) and any(qa.values())]
        if not qa_items:
            continue

        for idx, qa in enumerate(qa_items):
            qa_id = f"{slice_id}_{idx}"
            rows.append(
                {
                    "qa_id": qa_id,
                    "slice_id": slice_id,
                    "guideline_id": guideline_id,
                    "question": qa.get("question", ""),
                    "answer": qa.get("answer", ""),
                    "category": qa.get("category", ""),
                    "supporting_snippet": qa.get("supporting_snippet", ""),
                }
            )

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with output_csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["qa_id", "slice_id", "guideline_id", "question", "answer", "category", "supporting_snippet"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate guideline QA pairs from guideline text.")
    parser.add_argument("--input-jsonl", required=True, help="Path to guideline JSONL with fields text-guideline?, text.")
    parser.add_argument("--output-csv", default="data/processed/generated_guideline_QA.csv", help="CSV path for QA rows.")
    parser.add_argument("--output-pkl", default="data/processed/generated_guideline_QA.pkl", help="Pickle path for raw results.")
    parser.add_argument("--model", default="gpt-4o", help="Model to use for generation.")
    parser.add_argument("--max-concurrent", type=int, default=5, help="Max concurrent API calls.")
    parser.add_argument("--max-chars", type=int, default=2000, help="Max characters per slice.")
    parser.add_argument("--checkpoint-every", type=int, default=200, help="Checkpoint frequency (0 to disable).")
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key = require_env("OPENAI_API_KEY")

    input_path = Path(args.input_jsonl)
    output_csv = Path(args.output_csv)
    output_pkl = Path(args.output_pkl)
    partial_csv = output_csv.with_name(output_csv.stem + "_partial.csv")
    partial_pkl = output_pkl.with_name(output_pkl.stem + "_partial.pkl")

    guideline_data = load_guideline_jsonl(input_path)
    print(f"Loaded {len(guideline_data)} guideline documents")

    results = await process_all_guidelines(
        guideline_data=guideline_data,
        model=args.model,
        max_concurrent=args.max_concurrent,
        api_key=api_key,
        checkpoint_every=args.checkpoint_every,
        checkpoint_csv=partial_csv,
        checkpoint_pkl=partial_pkl,
        max_chars=args.max_chars,
    )

    output_pkl.parent.mkdir(parents=True, exist_ok=True)
    with output_pkl.open("wb") as f:
        pickle.dump(results, f)
    write_all_qa_to_csv(results, output_csv)
    print(f"Done. Results saved to {output_csv} and {output_pkl}")


if __name__ == "__main__":
    asyncio.run(main())
