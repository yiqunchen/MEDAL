import json
import asyncio
import pickle
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm
from typing import Dict

# ==== Load Data ====
with open("/Users/pql/Desktop/proj/test_4o_mini_on_4o_questions_with_predictions.json", "r") as f:
    full_data = json.load(f)

with open("/Users/pql/Desktop/proj/clean_pubmed_abstract_data_no_protocol.pkl", "rb") as f:
    abstract_data = pickle.load(f)


question_data = dict(full_data)

# Take a sample of 10 for testing
# question_data = dict(list(question_data.items())[:10])

# ==== Add abstract from DOI ====
for qid, item in question_data.items():
    doi = item.get("doi")
    if doi and doi in abstract_data:
        item["abstract"] = abstract_data[doi]["abstract"]
    else:
        item["abstract"] = "ABSTRACT NOT FOUND"

# ==== Async LLM Request Setup ====
api_key = "OPENAI_API_KEY_REDACTED" 
client = AsyncOpenAI(api_key=api_key)

async def get_response_async(client, prompt, model, semaphore):
    async with semaphore:
        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return completion.choices[0].message.content

async def evaluate_questions_parallel(question_data: Dict[str, dict], client, model="gpt-4o-mini", max_concurrent=6):
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def query_llm(qid: str, item: dict):
        question = item["question"]
        abstract = item.get("abstract", "")

        prompt = f"""You are a clinical research expert with comprehensive knowledge of systematic reviews, randomized controlled trials (RCTs), and observational studies. Your task is to assess a clinical question and return a structured judgment using evidence-based reasoning.

Here is a background abstract from the Cochrane review:

\"\"\"{abstract}\"\"\"

For the given question, provide:

1. A binary answer: \"Yes\", \"No\", or \"No Evidence\", based on whether the available evidence supports the claim.
2. The overall quality of evidence: choose one from \"High\", \"Moderate\", \"Low\", \"Very Low\", or \"Missing\", using standard evidence grading principles (e.g., GRADE).
3. Whether there is a discrepancy in findings across study types, such as a conflict between RCTs and observational studies: \"Yes\", \"No\", or \"Missing\".
4. A brief explanatory note justifying your assessment, if needed (e.g., contradictory evidence, limited data, or important nuances).

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
        try:
            response_str = await get_response_async(client, prompt, model, semaphore)
            response = json.loads(response_str)
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
                "ground_truth_answer": item.get("ground_truth_answer", ""),
                "ground_truth_evidence-quality": item.get("ground_truth_evidence-quality", ""),
                "ground_truth_discrepancy": item.get("ground_truth_discrepancy", ""),
                "ground_truth_notes": item.get("ground_truth_notes", ""),
                "doi": item.get("doi", "")
            }
        }

    tasks = [query_llm(qid, item) for qid, item in question_data.items()]
    pbar = tqdm(total=len(tasks), desc="Evaluating")

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.update(result)
        pbar.update(1)

    pbar.close()
    return results

# ==== Main entry point ====
async def main():
    results = await evaluate_questions_parallel(question_data, client)
    with open("/Users/pql/Desktop/proj/rag_eval_results_with_abstract.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
