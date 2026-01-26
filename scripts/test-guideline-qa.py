import json
import asyncio
import os
import pandas as pd
from typing import Dict
from tqdm.asyncio import tqdm
from openai import AsyncOpenAI

# === Load and preprocess CSV ===
csv_path = "aha_guideline_evidence_cleaned.csv"
df = pd.read_csv(csv_path)

# === Initialize OpenAI client ===
api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)

# === Prompt template ===
def build_prompt(recommendation):
    return f"""You are a clinical guideline reviewer.

You will be given one clinical recommendation. Based on your expertise and reasoning, answer the following:

1. Is this recommendation supported by current clinical evidence? Answer "Yes", "No", or "Unknown".
2. How strong is this recommendation? Give a number from 1 (very weak) to 5 (very strong).
3. What's the quality of the supporting evidence? Give a number from 1 (very low) to 5 (very high).
4. Is this recommendation supported by randomized controlled trials (RCTs)? Answer "Yes", "No", or "Unknown".
5. Is it supported by observational or nonrandomized studies? Answer "Yes", "No", or "Unknown".
6. Is it a concensus of expert opinion based on clinical experience? Answer "Yes", "No", or "Unknown".


Here is the recommendation:
\"\"\"{recommendation}\"\"\"

Return your answer in JSON format like this:
{{
  "supported": "Yes" or "No" or "Unknown",
  "recommendation_strength": 1-5,
  "evidence_quality":1-5,
  "based_on_rct": "Yes" or "No" or "Unknown",
  "based_on_observational": "Yes" or "No" or "Unknown",
  "based_on_expert_opinion": "Yes" or "No" or "Unknown"
}}"""

# === Async request handler ===
async def get_response_async(client, prompt, model, semaphore):
    async with semaphore:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return completion.choices[0].message.content

# === Main evaluation ===
async def evaluate_recommendations(model="gpt-4o-mini", max_concurrent=10):
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def evaluate_row(row):
        rid = row["id"]
        rec = row["Recommendation"]
        prompt = build_prompt(rec)

        try:
            response_str = await get_response_async(client, prompt, model, semaphore)
            response = json.loads(response_str)
        except Exception as e:
            response = {
                "supported": "ERROR",
                "recommendation_strength": "ERROR",
                "evidence_quality": "ERROR",
                "based_on_rct": "ERROR",
                "based_on_observational": "ERROR",
                "based_on_expert_opinion": "ERROR",
                "error": str(e)
            }

        results[rid] = {
            "recommendation": rec,
            "model_supported": response.get("supported", ""),
            "model_recommendation_strength": response.get("recommendation_strength", ""),
            "model_evidence_quality": response.get("evidence_quality", ""),
            "model_based_on_rct": response.get("based_on_rct", ""),
            "model_based_on_observational": response.get("based_on_observational", ""),
            "model_based_on_expert_opinion": response.get("based_on_expert_opinion", ""),
            "ground_truth_loe": row["LOE"],
            "ground_truth_cor": row["COR"],
            "source_file": row["SourceFile"]
        }

    tasks = [evaluate_row(row) for _, row in df.iterrows()]
    pbar = tqdm(total=len(tasks), desc="Evaluating Recommendations")
    

    for coro in asyncio.as_completed(tasks):
        await coro
        pbar.update(1)

    pbar.close()
    return results

# === Run the script ===
if __name__ == "__main__":
    output_file = "evidence_eval_results.json"
    results = asyncio.run(evaluate_recommendations())
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

