import json
import csv
import asyncio
import tqdm.asyncio
from datetime import datetime
from openai import AsyncOpenAI
import random
import pickle
from tqdm.asyncio import tqdm
import os
from medal import load_dotenv_if_present, require_env
import asyncio
from typing import Callable, Dict

async def get_response_async(client, prompt, model, semaphore):
    """Asynchronously get response from OpenAI API with semaphore control"""
    async with semaphore:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return completion.choices[0].message.content


async def evaluate_questions_parallel(
    question_data: Dict[str, dict],
    client,
    model: str,
    max_concurrent: int = 5
) -> Dict[str, dict]:
    """
    Evaluate a set of clinical questions using an LLM asynchronously with tqdm progress bar.

    Args:
        question_data (dict): Dict where keys are question IDs and values contain:
            - question, answer, evidence-quality, discrepancy, notes (ground truth)
        client: OpenAI client
        model (str): Name of the model (e.g., "gpt-4o", "gpt-4-turbo")
        max_concurrent (int): Max concurrent API calls allowed

    Returns:
        dict: Dictionary keyed by question ID, containing both model output and ground truth
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    total = len(question_data)
    results = {}

    async def query_llm(qid: str, item: dict) -> Dict[str, dict]:
        question = item["question"]
        prompt = f"""You are a clinical research expert with comprehensive knowledge of systematic reviews, randomized controlled trials (RCTs), and observational studies. Your task is to assess a clinical question and return a structured judgment using evidence-based reasoning.

For the given question, provide:

1. A binary answer: "Yes", "No", or "Not Enough Evidence", based on whether the available evidence supports the claim.
2. The overall quality of evidence: choose one from "High", "Moderate", "Low", "Very Low", or "Missing", using standard evidence grading principles (e.g., GRADE).
3. Whether there is a discrepancy in findings across study types, such as a conflict between RCTs and observational studies: "Yes", "No", or "Missing".
4. A brief explanatory note justifying your assessment, if needed (e.g., contradictory evidence, limited data, or important nuances).

Here is the clinical question:

\"\"\"{question}\"\"\"

Return your response in the following JSON format:

{{
  "question": "{question}",
  "answer": "Yes" or "No" or "No Enough Evidence",
  "evidence-quality": "High" or "Moderate" or "Low" or "Very Low" or "Missing",
  "discrepancy": "Yes" or "No" or "Missing",
  "notes": "Brief explanation if needed"
}}
"""
        try:
            response_json_str = await get_response_async(client, prompt, model, semaphore)
            import json
            response = json.loads(response_json_str)
        except Exception as e:
            response = {
                "question": question,
                "answer": "ERROR",
                "evidence-quality": "ERROR",
                "discrepancy": "ERROR",
                "notes": str(e)
            }

        return {
            qid: {
                "question": question,
                "model_answer": response.get("answer", ""),
                "model_evidence-quality": response.get("evidence-quality", ""),
                "model_discrepancy": response.get("discrepancy", ""),
                "model_notes": response.get("notes", ""),
                "ground_truth_answer": item.get("answer", ""),
                "ground_truth_evidence-quality": item.get("evidence-quality", ""),
                "ground_truth_discrepancy": item.get("discrepancy", ""),
                "ground_truth_notes": item.get("notes", ""),
                "doi": item.get("doi", "")
            }
        }

    # Create coroutine tasks
    tasks = [query_llm(qid, item) for qid, item in question_data.items()]

    # Track progress
    pbar = tqdm(total=len(tasks), desc="Evaluating")

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.update(result)
        pbar.update(1)

    pbar.close()
    return results

load_dotenv_if_present()
OPENAI_API_KEY = require_env("OPENAI_API_KEY")
INPUT_PATH = os.getenv("EVAL_INPUT_JSON", "./data/processed/test-temp-4o-mini-async.json")
OUTPUT_PATH = os.getenv("EVAL_OUTPUT_JSON", "./data/runs/test_4o_mini_results.json")

with open(INPUT_PATH, "r") as f:
    question_data = json.load(f)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def main():
	# Run the evaluation
    results = await evaluate_questions_parallel(question_data, client, model="gpt-4o", max_concurrent=15)

	# Save to file
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

# Entry point
if __name__ == "__main__":
    asyncio.run(main())