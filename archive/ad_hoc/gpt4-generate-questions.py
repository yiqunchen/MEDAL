import json
import csv
import asyncio
import tqdm.asyncio
from datetime import datetime
from openai import AsyncOpenAI
import random
import pickle
import os
from medal import load_dotenv_if_present, require_env
API_KEY = None
random.seed(2025)
base_model = 'gpt-4o'

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

async def process_abstract(doi, abstract_data, client, model, semaphore):
    """Process a single abstract and return the results"""
    abstract_text = abstract_data.get("abstract", "")
    if not abstract_text:
        return None

    prompt = f"""
    You are an expert clinical research assistant and medical researcher.
    
    Given the following abstract, generate a structured set of 2-4 challenging questions that assess intrinsic clinical understanding. Focus on:
    
    1. Key results and conclusions stated in the abstract.
    2. Contrasts or discrepancies between observational study findings and randomized clinical trial (RCT) results—especially if the conclusions differ.
    3. Clinical reasoning and decision-making implications based on the findings.
    4. Do NOT ask questions about general evidence quality directly, that should be folded under the "evidence-quality" in the output.
    
    Each question should be:
    
    - Challenging and specific. The questions should be asked in the context of *General knowledge* instead of being over-indexed on a single review.
    - Always include the question if RCT results differ from those obtained in observational studies. 
    - Phrased in a general clinical knowledge setting and AVOID meta-analysis jargons such as 
    "statistically significant", "systematic research bias", "based on this review", "based on this study" or 
    "does this study", "is there enough evidence from this study", "observational studies", "RCT", "controlled trials".
    - Do not start questions with forms like "based on this work", "is there existing studies", these are less interesting.
    - Example questions should look more like "Does doing A help with B (in context C)", "Is A associated with B (in context C)" as opposed to "Does this review provide high evidence".
    - Answerable directly or inferable from the abstract, this should be in forms of "Yes/No/No Evidence"
    - Optionally, if it is mentioned in the text, include a flag for evidence quality into "High/Moderate/Low/Very Low" (akin to the GRADE approach for evidence evaluation).  "Missing" if it's not present
    - Optionally, include a flag like "Discrepancy: Yes/No" to indicate if the question relates to conflicting evidence. "Missing" if it's not present.
    - In the "notes" part, include cited effect size and confidence interval if applicable.
    
    Return a JSON list of 2 to 4 Q&A pairs, depending on how information rich the abstract is, each formatted as follows:
    {{
      "question": "...",
      "answer": "Yes" or "No" or "No Evidence",
      "evidence-quality": "High" or "Moderate" or "Low" or "Very Low" or "Missing",
      "discrepancy": "Yes" or "No" or "Missing",
      "notes": "Brief explanation if needed"
    }}
    
    Abstract:
    \"\"\"
    {abstract_text}
    \"\"\"
    """
    
    try:
        result = await get_response_async(client, prompt, model, semaphore)
        qa_list = json.loads(result)
        return qa_list
    except Exception as e:
        print(f"Error with DOI {doi}: {e}")
        return None

async def process_all_abstracts(pubmed_abstract_data, model, max_concurrent=8, api_key=None):
    """Process all abstracts asynchronously with a semaphore limiting concurrent requests."""
    # Initialize async OpenAI client
    client = AsyncOpenAI(api_key=api_key)
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    tasks = {}
    for doi, abstract_data in pubmed_abstract_data.items():
        # Schedule each abstract processing as a task
        task = asyncio.create_task(process_abstract(doi, abstract_data, client, model, semaphore))
        tasks[doi] = task

    results = {}
    pbar = tqdm.tqdm(total=len(tasks), desc="Processing abstracts")
    
    # Use asyncio.as_completed to process tasks as they finish
    for doi, task in tasks.items():
        try:
            result = await task
            if result:
                results[doi] = result
        except Exception as e:
            print(f"Task error for DOI {doi}: {e}")
        finally:
            pbar.update(1)
    
    pbar.close()
    return results

def write_all_qa_to_csv(results, pubmed_abstract_data, output_csv_path):
    """
    Writes a CSV with all QA pairs, including the abstract and publication year.
    
    Parameters:
    - results: dict of {doi: qa_list}
    - pubmed_abstract_data: dict of {doi: metadata dict with 'abstract' and 'publication_year'}
    - output_csv_path: path to write the CSV
    """
    rows_for_csv = []

    for doi, qa_list in results.items():
        # Skip if no results for this DOI
        if not qa_list:
            continue
            
        # Get abstract and publication year
        abstract_text = ""
        publication_year = ""
        if doi in pubmed_abstract_data:
            abstract_data = pubmed_abstract_data[doi]
            abstract_text = abstract_data.get("abstract", "")
            publication_year = abstract_data.get("publication_year", "")
        
        # Normalize qa_list format
        if isinstance(qa_list, dict) and "questions" in qa_list:
            qa_items = qa_list["questions"]
        elif isinstance(qa_list, list):
            qa_items = qa_list
        elif isinstance(qa_list, dict) and "question" in qa_list:
            qa_items = [qa_list]  # wrap single QA dict in list
        else:
            continue  # skip unrecognized format
        
        # Add each QA pair as a row
        for qa in qa_items:
            rows_for_csv.append({
                "doi": doi,
                "publication_year": publication_year,
                "abstract": abstract_text,
                "question": qa.get("question", ""),
                "answer": qa.get("answer", ""),
                "evidence-quality": qa.get("evidence-quality", "Missing"),
                "discrepancy": qa.get("discrepancy", "Missing"),
                "notes": qa.get("notes", "")
            })

    # Write to CSV
    with open(output_csv_path, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = ["doi", "publication_year", "abstract", "question", "answer", "evidence-quality", "discrepancy", "notes"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_for_csv)


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-pkl", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-pkl", required=True)
    parser.add_argument("--model", default=base_model)
    parser.add_argument("--max-concurrent", type=int, default=8)
    args = parser.parse_args()

    load_dotenv_if_present()
    api_key_env = require_env("OPENAI_API_KEY")

    with open(args.input_pkl, "rb") as f:
        clean_pubmed_abstract_data = pickle.load(f)
    # Replace these variables with your actual variables
    random.seed(202504)

    # sampled_dois = random.sample(list(clean_pubmed_abstract_data.keys()), min(20, len(clean_pubmed_abstract_data)))
    # sampled_data = {doi: clean_pubmed_abstract_data[doi] for doi in sampled_dois}
    

    # Process all abstracts with 10 concurrent requests
    results = await process_all_abstracts(
        pubmed_abstract_data=clean_pubmed_abstract_data,
        model=args.model,
        max_concurrent=args.max_concurrent,
        api_key=api_key_env,
    )

    with open(args.out_pkl, 'wb') as f:
        pickle.dump(results, f)
    
    # Write all results to CSV, including publication year
    write_all_qa_to_csv(
        results,
        clean_pubmed_abstract_data,
        args.out_csv,
    )

# Run the main async function
if __name__ == "__main__":
    asyncio.run(main())