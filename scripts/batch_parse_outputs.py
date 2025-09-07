#!/usr/bin/env python
import sys
from pathlib import Path as _P
ROOT_DIR = _P(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import argparse
import json
from pathlib import Path
from typing import Dict, Tuple


def load_ground_truth_map(input_jsonl: Path) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    by_id: Dict[str, dict] = {}
    by_doi: Dict[str, dict] = {}
    with input_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if "id" in item and item["id"]:
                by_id[str(item["id"])]= item
            if "doi" in item and item["doi"]:
                by_doi[str(item["doi"])]= item
    return by_id, by_doi


def parse_custom_id(custom_id: str) -> str:
    # Expecting format "qid:<identifier>"
    if custom_id.startswith("qid:"):
        return custom_id.split(":", 1)[1]
    return custom_id


def extract_message_json(content_text: str) -> dict:
    try:
        return json.loads(content_text)
    except Exception:
        # Return as best-effort wrapper
        return {"raw": content_text}


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse OpenAI Batch results into merged prediction/ground-truth files")
    parser.add_argument("--input-jsonl", required=True, help="Original QAPair JSONL used to build batch")
    parser.add_argument("--batch-results-jsonl", required=True, help="Results JSONL downloaded from batch job")
    parser.add_argument("--out-pred-jsonl", required=True, help="Path to write normalized predictions JSONL")
    parser.add_argument("--out-merged-jsonl", required=True, help="Path to write merged GT+pred JSONL")
    args = parser.parse_args()

    input_path = Path(args.input_jsonl)
    results_path = Path(args.batch_results_jsonl)
    out_pred_path = Path(args.out_pred_jsonl)
    out_merged_path = Path(args.out_merged_jsonl)
    out_pred_path.parent.mkdir(parents=True, exist_ok=True)
    out_merged_path.parent.mkdir(parents=True, exist_ok=True)

    by_id, by_doi = load_ground_truth_map(input_path)

    with results_path.open("r", encoding="utf-8") as r, \
         out_pred_path.open("w", encoding="utf-8") as wpred, \
         out_merged_path.open("w", encoding="utf-8") as wmerge:

        for line in r:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            custom_id = obj.get("custom_id") or obj.get("id") or ""
            key = parse_custom_id(custom_id)

            # default prediction structure
            pred = {
                "key": key,
                "custom_id": custom_id,
                "status": None,
                "error": None,
                "model_answer": None,
                "model_evidence-quality": None,
                "model_discrepancy": None,
                "model_notes": None,
            }

            if "error" in obj and obj["error"]:
                pred["status"] = "error"
                pred["error"] = obj["error"]
            else:
                resp = obj.get("response", {})
                pred["status"] = f"{resp.get('status_code')}"
                body = resp.get("body", {})
                try:
                    content_text = ""
                    if obj.get("url") == "/v1/responses" or body.get("id", "").startswith("resp_"):
                        # Responses API shape
                        output = body.get("output") or body.get("content") or []
                        parts = []
                        for item in output:
                            for c in item.get("content", []):
                                if "text" in c:
                                    t = c["text"]
                                    parts.append(t.get("value") if isinstance(t, dict) else str(t))
                        content_text = "\n".join(parts)
                    else:
                        # Chat Completions
                        content_text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                    data = extract_message_json(content_text) if content_text else {}
                    pred["model_answer"] = data.get("answer")
                    pred["model_evidence-quality"] = data.get("evidence-quality")
                    pred["model_discrepancy"] = data.get("discrepancy")
                    pred["model_notes"] = data.get("notes")
                except Exception as e:
                    pred["error"] = f"parse_error: {e}"

            # write prediction line
            wpred.write(json.dumps(pred) + "\n")

            # merge with ground truth if found
            gt = by_id.get(key) or by_doi.get(key)
            if gt:
                merged = {
                    "id": gt.get("id"),
                    "doi": gt.get("doi"),
                    "question": gt.get("question"),
                    "ground_truth_answer": gt.get("answer"),
                    "ground_truth_evidence-quality": gt.get("evidence-quality"),
                    "ground_truth_discrepancy": gt.get("discrepancy"),
                    "model_answer": pred.get("model_answer"),
                    "model_evidence-quality": pred.get("model_evidence-quality"),
                    "model_discrepancy": pred.get("model_discrepancy"),
                    "model_notes": pred.get("model_notes"),
                    "status": pred.get("status"),
                    "custom_id": pred.get("custom_id"),
                    "error": pred.get("error"),
                }
                wmerge.write(json.dumps(merged) + "\n")


if __name__ == "__main__":
    main()


