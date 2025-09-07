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
from typing import Callable, Dict
import aiohttp
import json
import re

async def get_response_async(prompt, model, semaphore, api_key):
    """Asynchronously get response from Claude API with semaphore control"""
    try:
        async with semaphore:
            headers = {
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"  # This is the API version, not the model version
            }
            
            # Format the prompt to request JSON output - be VERY explicit
            json_prompt = prompt + "\n\nIMPORTANT: Your response MUST be a valid JSON object with no additional text before or after. Do not add explanations or markdown formatting around the JSON."
            
            payload = {
                "model": model,  # "claude-3-7-sonnet-20250219"
                "messages": [
                    {"role": "user", "content": json_prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 2000,
                "system": "You are an expert clinical research assistant and medical researcher. You MUST respond with valid JSON only, no preamble or explanation. Always structure your responses as valid parseable JSON with no additional text."
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.anthropic.com/v1/messages",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            
                            # Get the response text
                            response_text = result["content"][0]["text"].strip()
                            
                            # Debug logging
                            response_preview = response_text[:100] + "..." if len(response_text) > 100 else response_text
                            #print(f"Claude response preview: {response_preview}")
                            
                            # Try to extract JSON if it's wrapped in markdown code blocks
                            if response_text.startswith("```json") and response_text.endswith("```"):
                                response_text = response_text[7:-3].strip()
                            elif response_text.startswith("```") and response_text.endswith("```"):
                                response_text = response_text[3:-3].strip()
                                
                            # If empty response, return error JSON
                            if not response_text:
                                print("Empty response from Claude API")
                                return json.dumps({
                                    "answer": "ERROR",
                                    "evidence-quality": "ERROR",
                                    "discrepancy": "ERROR",
                                    "notes": "Empty response from Claude API"
                                })
                                
                            # Try to parse as JSON to verify it's valid
                            try:
                                json.loads(response_text)
                                return response_text
                            except json.JSONDecodeError as e:
                                print(f"Invalid JSON returned by Claude: {e}")
                                print(f"Raw text: {response_text}")
                                
                                # Try to extract JSON if there's text before or after
                                json_match = re.search(r'({[\s\S]*})', response_text)
                                if json_match:
                                    potential_json = json_match.group(1)
                                    try:
                                        json.loads(potential_json)
                                        return potential_json
                                    except:
                                        pass
                                
                                # If we can't parse it, create a fallback JSON
                                return json.dumps({
                                    "answer": "ERROR",
                                    "evidence-quality": "ERROR",
                                    "discrepancy": "ERROR",
                                    "notes": f"Failed to parse Claude response as JSON: {e}"
                                })
                        else:
                            error_text = await response.text()
                            print(f"Claude API error: {response.status} - {error_text}")
                            return json.dumps({
                                "answer": "ERROR",
                                "evidence-quality": "ERROR",
                                "discrepancy": "ERROR",
                                "notes": f"Claude API error: {response.status}"
                            })
            except Exception as e:
                print(f"Request error: {e}")
                return json.dumps({
                    "answer": "ERROR",
                    "evidence-quality": "ERROR",
                    "discrepancy": "ERROR",
                    "notes": f"Request error: {str(e)}"
                })
    except Exception as e:
        print(f"Semaphore error: {e}")
        return json.dumps({
            "answer": "ERROR",
            "evidence-quality": "ERROR",
            "discrepancy": "ERROR",
            "notes": f"Semaphore error: {str(e)}"
        })

async def evaluate_questions_parallel(
    question_data: Dict[str, dict],
    api_key: str,
    model: str = "claude-3-7-sonnet-20250219",
    max_concurrent: int = 5
) -> Dict[str, dict]:
    """
    Evaluate a set of clinical questions using Claude asynchronously with tqdm progress bar.

    Args:
        question_data (dict): Dict where keys are question IDs and values contain:
            - question, answer, evidence-quality, discrepancy, notes (ground truth)
        api_key (str): Claude API key
        model (str): Name of the Claude model (e.g., "claude-3-7-sonnet-20250219")
        max_concurrent (int): Max concurrent API calls allowed

    Returns:
        dict: Dictionary keyed by question ID, containing both model output and ground truth
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    # Define the nested query_llm function - this is correctly scoped
    async def query_llm(qid: str, item: dict) -> Dict[str, dict]:
        question = item["question"]
        prompt = f"""You are a clinical research expert with comprehensive knowledge of systematic reviews, randomized controlled trials (RCTs), and observational studies. Your task is to assess a clinical question and return a structured judgment using evidence-based reasoning.

For the given question, provide:

1. A categorical answer: "Yes", "No", or "No Evidence", based on whether the available evidence supports the claim.
2. The overall quality of evidence: choose one from "High", "Moderate", "Low", "Very Low", or "Missing", using standard evidence grading principles (e.g., GRADE).
3. Whether there is a discrepancy in findings across study types, such as a conflict between RCTs and observational studies: "Yes", "No", or "Missing".
4. A brief explanatory note justifying your assessment, if needed (e.g., contradictory evidence, limited data, or important nuances).

Here is the clinical question:

\"\"\"{question}\"\"\"

Return your response in the following JSON format ONLY, with NO additional text or explanation outside the JSON object:

{{
  "question": "{question}",
  "answer": "Yes" or "No" or "No Evidence",
  "evidence-quality": "High" or "Moderate" or "Low" or "Very Low" or "Missing",
  "discrepancy": "Yes" or "No" or "Missing",
  "notes": "Brief explanation if needed"
}}
"""
        try:
            response_json_str = await get_response_async(prompt, model, semaphore, api_key)
            if response_json_str:
                try:
                    response = json.loads(response_json_str)
                    if not isinstance(response, dict):
                        raise ValueError("Response is not a dictionary")
                    
                    # Verify required fields are present
                    required_fields = ["answer", "evidence-quality", "discrepancy"]
                    for field in required_fields:
                        if field not in response:
                            response[field] = "ERROR"
                    
                    # Add question field if missing
                    if "question" not in response:
                        response["question"] = question
                    
                    # Add notes field if missing
                    if "notes" not in response:
                        response["notes"] = ""
                    
                except json.JSONDecodeError as e:
                    print(f"JSON parsing error for question ID {qid}: {e}")
                    print(f"Raw response: {response_json_str[:200]}...")
                    response = {
                        "question": question,
                        "answer": "ERROR",
                        "evidence-quality": "ERROR",
                        "discrepancy": "ERROR",
                        "notes": f"Error parsing JSON: {str(e)}"
                    }
                except Exception as e:
                    response = {
                        "question": question,
                        "answer": "ERROR",
                        "evidence-quality": "ERROR",
                        "discrepancy": "ERROR", 
                        "notes": f"Error validating response: {str(e)}"
                    }
            else:
                response = {
                    "question": question,
                    "answer": "ERROR",
                    "evidence-quality": "ERROR",
                    "discrepancy": "ERROR",
                    "notes": "Failed to get response from API"
                }
        except Exception as e:
            response = {
                "question": question,
                "answer": "ERROR",
                "evidence-quality": "ERROR",
                "discrepancy": "ERROR",
                "notes": f"Exception: {str(e)}"
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
                # "ground_truth_notes": item.get("notes", ""),
                "doi": item.get("doi", "")
            }
        }

    # Create coroutine tasks
    tasks = [query_llm(qid, item) for qid, item in question_data.items()]

    # Track progress
    pbar = tqdm(total=len(tasks), desc="Evaluating")

    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            results.update(result)
        except Exception as e:
            print(f"Task error: {e}")
        finally:
            pbar.update(1)

    pbar.close()
    return results

async def main():
    load_dotenv_if_present()
    INPUT_PATH = os.getenv("EVAL_INPUT_JSONL", "./data/processed/test-4o-full-test-negated-dataset.jsonl")
    OUTPUT_PATH = os.getenv("EVAL_OUTPUT_JSON", "./data/runs/test_claude_3_7_sonnet_predictions_negative.json")
    with open(INPUT_PATH, "r") as f:
        question_data = [json.loads(line) for line in f]
    # question_data = random.sample(question_data, 2)
    question_data = {f"{i}": data for i, data in enumerate(question_data)}
    # Sample 20 items if needed
    # sampled_data = dict(random.sample(list(question_data.items()), 20))
    
    # Your Claude API key
    api_key = require_env("ANTHROPIC_API_KEY")
    
    # Run the evaluation with Claude 3.7 Sonnet
    results = await evaluate_questions_parallel(
        question_data=question_data,  # or sampled_data if you want to sample
        api_key=api_key,
        model="claude-3-7-sonnet-20250219",
        max_concurrent=3
    )

    # Save to file
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    
    print("Evaluation complete")

# Entry point
if __name__ == "__main__":
    asyncio.run(main())
