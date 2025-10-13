import json
import csv
import asyncio
import tqdm.asyncio
from datetime import datetime
from openai import AsyncOpenAI
import random
import pickle
import os

API_KEY = "OPENAI_API_KEY_REDACTED"
random.seed(2025)
base_model = 'gpt-4o'

# ---- Async OpenAI Call with Retry ----
async def get_response_async(client, prompt, model, semaphore, max_retries=3):
    async with semaphore:
        for attempt in range(max_retries):
            try:
                completion = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                return completion.choices[0].message.content
            except Exception as e:
                print(f"Error on attempt {attempt+1}: {e}")
                if attempt < max_retries - 1:
                    print(f"Sleeping 10s before retrying...")
                    await asyncio.sleep(10)
                else:
                    print("Max retries exceeded.")
                    raise e

# ---- Process Single Article ----
async def process_article(doi, article_data, client, model, semaphore):
    title = article_data.get("title", "")
    abstract_text = article_data.get("abstract", "")
    if not abstract_text or not title:
        return None

    prompt = f"""
    Please assign one or two of the following topics to the article based on its title and abstract:
    Topics:
    - Allergy and Intolerance
    - Blood Disorders
    - Cancer
    - Child Health
    - Complementary and Alternative Medicine
    - Consumer and Communication Strategies
    - Dentistry and Oral Health
    - Developmental, Psychosocial and Learning Problems
    - Diagnosis
    - Ear, Nose and Throat
    - Effective Practice and Health Systems
    - Endocrine and Metabolic
    - Eyes and Vision
    - Gastroenterology and Hepatology
    - Genetic Disorders
    - Gynaecology
    - Health and Safety at Work
    - Health Professional Education
    - Heart and Circulation
    - Infectious Disease
    - Insurance Medicine
    - Kidney Disease
    - Lungs and Airways
    - Mental Health
    - Methodology
    - Neonatal Care
    - Neurology
    - Orthopaedics and Trauma
    - Pain and Anaesthesia
    - Pregnancy and Childbirth
    - Public Health
    - Reproductive and Sexual Health
    - Rheumatology
    - Skin Disorders
    - Tobacco, Drugs and Alcohol
    - Urology
    - Wounds

    Title: '{title}'
    Abstract: "{abstract_text}"

    Return the result as JSON with the following format:
    {{
      "one_topic_assignment": "<one topic from the list>",
      "two_topic_assignment": ["<first topic>", "<second topic>"]
    }}
    """

    try:
        result = await get_response_async(client, prompt, model, semaphore)
        topic_assignment = json.loads(result)
        return topic_assignment
    except Exception as e:
        print(f"Error with DOI {doi}: {e}")
        return None

# ---- Save Temporary Checkpoints ----
def save_temp_results(results, save_path):
    with open(save_path, 'wb') as f:
        pickle.dump(results, f)
    print(f"Temporary checkpoint saved to {save_path}")

# ---- Process All Articles ----
async def process_all_articles(pubmed_abstract_data, model, max_concurrent=2, api_key=None, checkpoint_every=500):
    client = AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = {}
    for doi, article_data in pubmed_abstract_data.items():
        task = asyncio.create_task(process_article(doi, article_data, client, model, semaphore))
        tasks[doi] = task

    results = {}
    pbar = tqdm.tqdm(total=len(tasks), desc="Processing articles")
    temp_save_path = '/Users/pql/Desktop/proj/gpt4o-topic-assignments-temp.pkl'

    for i, (doi, task) in enumerate(tasks.items(), 1):
        try:
            result = await task
            if result:
                results[doi] = result
        except Exception as e:
            print(f"Task error for DOI {doi}: {e}")
        finally:
            pbar.update(1)

        if i % checkpoint_every == 0:
            save_temp_results(results, temp_save_path)

    pbar.close()
    return results

# ---- Write Results to CSV ----
def write_classification_to_csv(results, pubmed_abstract_data, output_csv_path):
    rows_for_csv = []

    for doi, classification in results.items():
        if not classification:
            continue

        title = pubmed_abstract_data.get(doi, {}).get("title", "")
        abstract_text = pubmed_abstract_data.get(doi, {}).get("abstract", "")

        rows_for_csv.append({
            "doi": doi,
            "title": title,
            "abstract": abstract_text,
            "one_topic_assignment": classification.get("one_topic_assignment", ""),
            "two_topic_assignment": ", ".join(classification.get("two_topic_assignment", []))
        })

    with open(output_csv_path, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = ["doi", "title", "abstract", "one_topic_assignment", "two_topic_assignment"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_for_csv)

# ---- Main Entry ----
async def main():
    with open("/Users/pql/Desktop/proj/clean_pubmed_abstract_data_no_protocol.pkl", "rb") as f:
        clean_pubmed_abstract_data = pickle.load(f)

    random.seed(202504)
    #clean_pubmed_abstract_data = {doi: clean_pubmed_abstract_data[doi] for doi in random.sample(list(clean_pubmed_abstract_data.keys()), 10)}

    results = await process_all_articles(
        pubmed_abstract_data=clean_pubmed_abstract_data,
        model=base_model,
        max_concurrent=2,
        api_key=API_KEY,
        checkpoint_every=500
    )

    with open('/Users/pql/Desktop/proj/gpt4o-topic-assignments.pkl', 'wb') as f:
        pickle.dump(results, f)

    write_classification_to_csv(
        results,
        clean_pubmed_abstract_data,
        '/Users/pql/Desktop/proj/gpt4o-topic-assignments.csv'
    )
    print("✅ All done and saved.")

if __name__ == "__main__":
    asyncio.run(main())
