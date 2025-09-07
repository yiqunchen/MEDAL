import pickle
import argparse
import asyncio
import json
import os
import time
import json
import requests
from collections import defaultdict
from urllib.error import HTTPError
from urllib.parse import quote_plus
from Bio import Entrez
import numpy as np
import pandas as pd
import random
import tqdm
import openai
import os
import json
import time
import asyncio
import json
import time
from openai import OpenAI
import tqdm.asyncio  # tqdm with async support


from openai import OpenAI, AsyncOpenAI
# json_path = "/Users/yiquntchen/Downloads/test-temp-4o-one-question-async.json"  

import os
from medal import load_dotenv_if_present, require_env
INPUT_PATH = os.getenv("NEGATE_INPUT_JSONL", "./data/processed/test-4o-full-test-negated-dataset.jsonl")
with open(INPUT_PATH, "r") as f:
    question_data = [json.loads(line) for line in f]
converted_dict = {f"{i}": data for i, data in enumerate(question_data)}

# # Replace with desired output path
# with open(json_path, 'rb') as f:
#     converted_dict = json.load(f)
# Open AI API key
load_dotenv_if_present()
api_key = require_env("OPENAI_API_KEY")
# --- Functions from earlier ---
def generate_negation_prompt(entry):
    prompt = f"""
You are a clinical research expert with comprehensive knowledge of systematic reviews, randomized controlled trials (RCTs), 
and observational studies. Your task is to negate specific fields in a medical evidence summary while preserving the integrity of 
the original data.

Here is the medical evidence summary you need to analyze:
{{
  "doi": "{entry['doi']}",
  "question": "{entry['question']}",
  "answer": "{entry['answer']}",
  "evidence-quality": "{entry['evidence-quality']}",
  "discrepancy": "{entry['discrepancy']}",
}}

Your objective is to negate the 'question' and 'answer' fields in this summary according to the following rules:

1. NEGATED_QUESTION:
   - If the question is in the form "if A improves B", negate it to "if A reduces B". 
   - Pairs like improve/reduce, increase/decrease, promote/inhibit, etc are PREFERRED over improve/does not improve.
   - The negation must be *logically correct*. That is, the original question and answer need to imply that the negated question and answer are correct.
   - If the question is in another form, attempt to negate its core meaning using a verb while keeping other parts of the question mostly the same.
   - If negation is not clear or possible, use "Not applicable" as the NEGATED_QUESTION.

2. NEGATED_ANSWER: 
   - If the NEGATED_QUESTION is "Not applicable", the answer should be "Not applicable".
   - If the answer is "Yes", change it to "No".
   - If the answer is "No", change it to "Yes".
   - If the answer is "No Evidence", leave it unchanged.

All other fields, including the original 'question', 'discrepancy', and 'evidence-quality', must remain exactly the same.

Provide the negated summary in the following JSON format:

{{
  "doi": "[Original DOI]",
  "question": "[NEGATED_QUESTION]",
  "answer": "[NEGATED_ANSWER]",
  "original_question": {entry['question']},
  "original_answer": {entry['answer']},
  "evidence-quality": "[Original evidence-quality]",
  "discrepancy": "[Original discrepancy]"
}}

Remember to replace the placeholders in square brackets with the appropriate content from the original summary or your negated versions.
"""
    return prompt.strip()

def check_negation_validity(original_answer, negated_answer):
    if original_answer == "Yes" and negated_answer == "No":
        return True
    elif original_answer == "No" and negated_answer == "Yes":
        return True
    elif original_answer == "No Evidence" and negated_answer == "No Evidence":
        return True
    else:
        return False

def process_llm_response(original_entry, llm_response_dict):
    original_answer = original_entry["answer"]
    negated_answer = llm_response_dict["answer"]
    valid = check_negation_validity(original_answer, negated_answer)
    llm_response_dict["negation-valid"] = valid
    return llm_response_dict

async def call_openai_with_prompt(prompt, model, client, semaphore):
    try:
        async with semaphore:
            completion = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        raw_content = completion.choices[0].message.content.strip()
        return json.loads(raw_content)
    except Exception as e:
        print(f"❌ OpenAI call failed: {e}")
        # raise

# --- Process a single entry asynchronously ---
async def process_entry(key, entry, model, client, semaphore):
    prompt = generate_negation_prompt(entry)
    try:
        llm_response = await call_openai_with_prompt(prompt, model, client, semaphore)
        processed = process_llm_response(entry, llm_response)
        return key, processed, None
    except Exception as e:
        return key, None, str(e)

# --- Final async driver function ---
async def generate_llm_responses_and_validate(converted_dict, model, api_key, max_concurrent_requests=5):
    from openai import OpenAI

    llm_responses = {}
    final_dataset = []
    invalid_cases = []
    error_cases = []

    client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(max_concurrent_requests)

    tasks = []
    for key, entry in converted_dict.items():
        tasks.append(process_entry(key, entry, model, client, semaphore))

    for future in tqdm.asyncio.tqdm(asyncio.as_completed(tasks), total=len(tasks)):
        key, processed, error = await future
        if error:
            print(f"❌ Failed to process key {key}: {error}")
            error_cases.append({
                "key": key,
                "entry": converted_dict[key],
                "error": error
            })
        else:
            llm_responses[key] = processed
            final_dataset.append(processed)
            if not processed.get("negation-valid", False):
                invalid_cases.append(processed)

    return final_dataset, invalid_cases, llm_responses, error_cases

# --- Example usage ---
if __name__ == "__main__":
    import random

    # Assume converted_dict is already defined elsewhere
    # For testing, you might sample a few entries:
    # sampled_data = dict(random.sample(list(converted_dict.items()), 10))
    
    # Define your API key and model name
    api_key = api_key
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-jsonl", required=True)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--max-concurrent", type=int, default=3)
    args = parser.parse_args()
    model = args.model

    # Run the async driver function
    final_dataset, invalid_cases, llm_responses, error_cases = asyncio.run(
        generate_llm_responses_and_validate(converted_dict, model, api_key, max_concurrent_requests=args.max_concurrent)
    )

    out_path = args.out_jsonl
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        for item in final_dataset:
            f.write(json.dumps(item) + "\n")
