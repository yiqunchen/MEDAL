#!/usr/bin/env python
"""
Evaluate clinical QA dataset using OpenRouter API.
Supports Claude Sonnet 4.5, DeepSeek, and other models via OpenRouter.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from tqdm import tqdm


EVAL_PROMPT = """
You are a clinical research expert with knowledge of systematic reviews, RCTs, and observational studies.
Task: Given a clinical question, return a JSON with keys question, answer, evidence-quality, discrepancy, notes.
Allowed values:
- answer: Yes | No | No Evidence
- evidence-quality: High | Moderate | Low | Very Low | Missing
- discrepancy: Yes | No | Missing
""".strip()


def make_openrouter_client(api_key: str) -> AsyncOpenAI:
    """Create OpenRouter client using OpenAI SDK."""
    return AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com"),
            "X-Title": os.getenv("OPENROUTER_X_TITLE", "MEDAL Evaluation"),
        }
    )


async def bounded_json_chat_completion(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    semaphore: asyncio.Semaphore,
    temperature: Optional[float] = 0.2,
) -> str:
    """Call OpenRouter chat completion with rate limiting."""
    async with semaphore:
        try:
            # Add explicit JSON instruction to prompt
            json_prompt = f"{prompt}\n\nYou must respond with valid JSON only."

            completion = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": json_prompt}],
                temperature=temperature,
            )
            content = completion.choices[0].message.content

            # Try to extract JSON if wrapped in markdown code blocks
            if content and "```json" in content:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
            elif content and "```" in content:
                import re
                json_match = re.search(r'```\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)

            return content
        except Exception as e:
            print(f"Error in API call: {e}")
            raise


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate using OpenRouter API")
    parser.add_argument("--input-jsonl", required=True, help="Input QA JSONL file")
    parser.add_argument("--out-json", required=True, help="Output results JSON file")
    parser.add_argument(
        "--model",
        default="anthropic/claude-sonnet-4.5",
        help="OpenRouter model ID (e.g., anthropic/claude-sonnet-4.5, deepseek/deepseek-chat)"
    )
    parser.add_argument("--max-concurrent", type=int, default=15, help="Max concurrent requests")
    parser.add_argument("--limit", type=int, help="Limit number of questions to evaluate (for testing)")
    args = parser.parse_args()

    # Get API key from environment
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    client = make_openrouter_client(api_key)
    semaphore = asyncio.Semaphore(args.max_concurrent)

    # Load questions
    records = []
    with open(args.input_jsonl, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.limit and i >= args.limit:
                break
            try:
                item = json.loads(line)
                records.append((str(i), item))
            except Exception as e:
                print(f"Error parsing line {i}: {e}")
                pass

    print(f"Loaded {len(records)} questions")
    print(f"Using model: {args.model}")
    print(f"Max concurrent: {args.max_concurrent}")

    # Load checkpoint if exists
    out_path = Path(args.out_json)
    checkpoint_path = out_path.parent / f"{out_path.stem}.checkpoint.json"
    completed_indices = set()
    out = {}

    if checkpoint_path.exists():
        print(f"Loading checkpoint from {checkpoint_path}")
        with checkpoint_path.open("r", encoding="utf-8") as f:
            out = json.load(f)
            completed_indices = set(out.keys())
        print(f"Resuming from checkpoint: {len(completed_indices)} already completed")

    # Filter out already completed items
    records_to_process = [(idx, item) for idx, item in records if idx not in completed_indices]
    print(f"Processing {len(records_to_process)} questions ({len(completed_indices)} already completed)")

    async def evaluate_one(idx: str, item: dict, pbar: tqdm):
        q = item["question"]
        prompt = f"{EVAL_PROMPT}\n\nQuestion:\n\"\"\"{q}\"\"\""
        try:
            content = await bounded_json_chat_completion(
                client, args.model, prompt, semaphore, temperature=0.2
            )
            resp = json.loads(content)
        except Exception as e:
            resp = {
                "question": q,
                "answer": "ERROR",
                "evidence-quality": "ERROR",
                "discrepancy": "ERROR",
                "notes": str(e),
            }

        result = {
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

        pbar.update(1)
        return result

    # Run evaluations with progress bar and checkpointing
    tasks = []
    checkpoint_counter = 0
    checkpoint_frequency = 50  # Save checkpoint every 50 completions

    with tqdm(
        total=len(records),
        initial=len(completed_indices),
        desc=f"Evaluating with {args.model}",
        unit="question"
    ) as pbar:
        tasks = [evaluate_one(idx, item, pbar) for idx, item in records_to_process]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            out.update(result)
            checkpoint_counter += 1

            # Save checkpoint periodically
            if checkpoint_counter >= checkpoint_frequency:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with checkpoint_path.open("w", encoding="utf-8") as w:
                    json.dump(out, w, indent=2)
                checkpoint_counter = 0

    # Save final results
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as w:
        json.dump(out, w, indent=2)

    # Remove checkpoint file on successful completion
    if checkpoint_path.exists():
        checkpoint_path.unlink()

    print(f"\nResults saved to {out_path}")

    # Calculate and print accuracy
    correct = 0
    total = 0
    for item in out.values():
        if item["model_answer"] != "ERROR":
            total += 1
            if item["model_answer"] == item["ground_truth_answer"]:
                correct += 1

    if total > 0:
        accuracy = correct / total
        print(f"\nAccuracy: {accuracy:.3f} ({correct}/{total})")


if __name__ == "__main__":
    asyncio.run(main())
