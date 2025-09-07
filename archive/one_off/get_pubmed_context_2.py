import json
import time
from Bio import Entrez
from tqdm import tqdm

Entrez.email = 'WangCan20@outlook.com'

# Paths
full_data_path = "/Users/pql/Desktop/proj/test_4o_mini_on_4o_questions_with_predictions.json"
context_save_path = "/Users/pql/Desktop/proj/pubmed_context_dataset.json"

# Load full question set
with open(full_data_path, "r") as f:
    full_data = json.load(f)

question_data = dict(full_data)

# Load existing retrieved context if available
try:
    with open(context_save_path, "r") as f:
        retrieved_context_data = json.load(f)
except FileNotFoundError:
    retrieved_context_data = {}

# Define PubMed retrieval function
def get_pubmed_abstracts(query: str, max_results: int = 3, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            search_handle = Entrez.esearch(db="pubmed", term=query, retmax=max_results, sort="relevance")
            search_results = Entrez.read(search_handle)
            pmids = search_results["IdList"]
            if not pmids:
                return "NO PUBMED RESULTS FOUND"
            fetch_handle = Entrez.efetch(db="pubmed", id=",".join(pmids), rettype="abstract", retmode="text")
            abstract_text = fetch_handle.read()
            return abstract_text.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                return f"ERROR retrieving PubMed abstracts: {e}"

# Continue retrieving abstracts
start_idx = len(retrieved_context_data)
all_items = list(question_data.items())
remaining_items = all_items[start_idx:]

for idx, (qid, item) in enumerate(tqdm(remaining_items, desc="Continuing PubMed retrieval", initial=start_idx, total=len(all_items))):
    if qid in retrieved_context_data:
        continue  # already done

    query = item["question"]
    pubmed_context = get_pubmed_abstracts(query)
    time.sleep(0.4)

    retrieved_context_data[qid] = {
        "question": query,
        "doi": item.get("doi", ""),
        "ground_truth_answer": item.get("ground_truth_answer", ""),
        "ground_truth_evidence-quality": item.get("ground_truth_evidence-quality", ""),
        "ground_truth_discrepancy": item.get("ground_truth_discrepancy", ""),
        "ground_truth_notes": item.get("ground_truth_notes", ""),
        "pubmed_context": pubmed_context
    }

    if (start_idx + idx) % 500 == 0:
        with open(context_save_path, "w") as f:
            json.dump(retrieved_context_data, f, indent=2)

# Final save
with open(context_save_path, "w") as f:
    json.dump(retrieved_context_data, f, indent=2)

print("✅ Continued and saved PubMed context dataset.")
