#!/usr/bin/env python
import sys
from pathlib import Path as _P
ROOT_DIR = _P(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional
import math

try:
    import matplotlib.pyplot as plt  # optional
except Exception:
    plt = None
try:
    import numpy as np  # optional
except Exception:
    np = None
try:
    from scipy import stats  # optional
except Exception:
    stats = None


YES_NO_NOE = {"Yes", "No", "No Evidence"}
QUALITY_SET = {"High", "Moderate", "Low", "Very Low", "Missing"}
DISC_SET = {"Yes", "No", "Missing"}


def normalize(s):
    if s is None:
        return None
    return str(s).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze prediction errors and produce summary CSVs")
    parser.add_argument("--merged-jsonl", required=True, help="Merged GT+pred JSONL from batch_parse_outputs.py")
    parser.add_argument("--out-dir", required=True, help="Directory to write CSV summaries and plots")
    parser.add_argument("--plot", action="store_true", help="If set, write PNG plots (requires matplotlib)")
    parser.add_argument("--metadata-jsonl", required=False, help="Optional metadata JSONL: {doi, field?, citation_count?, publication_year?}")
    args = parser.parse_args()

    merged_path = Path(args.merged_jsonl)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Optional metadata map by DOI
    meta_by_doi: dict = {}
    if args.metadata_jsonl:
        meta_path = Path(args.metadata_jsonl)
        if meta_path.exists():
            with meta_path.open("r", encoding="utf-8") as mf:
                for line in mf:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    d = item.get("doi")
                    if not d:
                        continue
                    meta_by_doi[str(d)] = item

    # Counters
    total = 0
    status_counter = Counter()
    answer_confusion = Counter()  # (gt, pred)
    quality_confusion = Counter()  # (gt, pred)
    disc_confusion = Counter()  # (gt, pred)
    error_examples = defaultdict(list)

    rows = []
    correct = 0
    field_counts = Counter()
    field_correct = Counter()
    citation_points = []  # (citation_count: float, correct: int)
    with merged_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            total += 1
            status = normalize(item.get("status"))
            status_counter[status] += 1

            gt_ans = normalize(item.get("ground_truth_answer"))
            gt_q = normalize(item.get("ground_truth_evidence-quality"))
            gt_d = normalize(item.get("ground_truth_discrepancy"))

            pd_ans = normalize(item.get("model_answer"))
            pd_q = normalize(item.get("model_evidence-quality"))
            pd_d = normalize(item.get("model_discrepancy"))

            is_correct = 0
            if gt_ans in YES_NO_NOE and pd_ans in YES_NO_NOE:
                answer_confusion[(gt_ans, pd_ans)] += 1
                if gt_ans == pd_ans:
                    correct += 1
                    is_correct = 1
            if gt_q in QUALITY_SET and pd_q in QUALITY_SET:
                quality_confusion[(gt_q, pd_q)] += 1
            if gt_d in DISC_SET and pd_d in DISC_SET:
                disc_confusion[(gt_d, pd_d)] += 1

            if pd_ans not in YES_NO_NOE:
                error_examples["invalid_answer"].append(item)
            if pd_q not in QUALITY_SET and pd_q is not None:
                error_examples["invalid_quality"].append(item)
            if pd_d not in DISC_SET and pd_d is not None:
                error_examples["invalid_discrepancy"].append(item)

            doi = item.get("doi")
            meta = meta_by_doi.get(str(doi), {}) if doi else {}
            field = str(meta.get("field")).strip() if meta.get("field") is not None else None
            citation_count = meta.get("citation_count") if isinstance(meta, dict) else None
            try:
                if citation_count is not None:
                    citation_count = float(citation_count)
            except Exception:
                citation_count = None

            if field:
                field_counts[field] += 1
                field_correct[field] += is_correct
            if citation_count is not None:
                citation_points.append((citation_count, is_correct))

            rows.append({
                "doi": doi,
                "question": item.get("question"),
                "gt_answer": gt_ans,
                "pred_answer": pd_ans,
                "gt_quality": gt_q,
                "pred_quality": pd_q,
                "gt_discrepancy": gt_d,
                "pred_discrepancy": pd_d,
                "status": status,
                "error": normalize(item.get("error")),
                "field": field,
                "citation_count": citation_count,
            })

    # Write per-example CSV
    csv_path = out_dir / "examples.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as w:
        fieldnames = list(rows[0].keys()) if rows else [
            "doi","question","gt_answer","pred_answer","gt_quality","pred_quality","gt_discrepancy","pred_discrepancy","status","error"
        ]
        writer = csv.DictWriter(w, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # Write status summary
    status_path = out_dir / "status_summary.csv"
    with status_path.open("w", newline="", encoding="utf-8") as w:
        writer = csv.writer(w)
        writer.writerow(["status", "count"])
        for k, v in status_counter.most_common():
            writer.writerow([k, v])

    # Write confusion matrices
    def write_confusion(path: Path, counts: Counter):
        with path.open("w", newline="", encoding="utf-8") as w:
            writer = csv.writer(w)
            writer.writerow(["gt", "pred", "count"])
            for (gt, pd), cnt in counts.most_common():
                writer.writerow([gt, pd, cnt])

    write_confusion(out_dir / "answer_confusion.csv", answer_confusion)
    write_confusion(out_dir / "quality_confusion.csv", quality_confusion)
    write_confusion(out_dir / "discrepancy_confusion.csv", disc_confusion)

    # Write a quick summary JSON
    summary = {
        "total": total,
        "status": dict(status_counter),
        "unique_questions": len({r.get("question") for r in rows}),
        "accuracy_answer": (correct / total) if total else None,
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as w:
        json.dump(summary, w, indent=2)

    print(f"Wrote: {csv_path}, {status_path}, confusion CSVs, and summary.json")

    # Optional plots
    if args.plot and plt is not None:
        # Status bar
        labels = list(status_counter.keys())
        values = [status_counter[k] for k in labels]
        plt.figure(figsize=(6,4))
        plt.bar(labels, values)
        plt.title("Status counts")
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(out_dir / "status_counts.png", dpi=150)
        plt.close()

        # Answer confusion heatmap-like CSV already exists; simple bar for correct vs incorrect
        plt.figure(figsize=(4,4))
        plt.bar(["correct", "incorrect"], [correct, max(total - correct, 0)])
        plt.title("Answer accuracy")
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(out_dir / "answer_accuracy.png", dpi=150)
        plt.close()

        # Accuracy by field (top 15)
        if field_counts:
            field_acc = []
            for k, cnt in field_counts.items():
                acc = (field_correct[k] / cnt) if cnt else 0.0
                field_acc.append((k, cnt, acc))
            field_acc.sort(key=lambda x: x[1], reverse=True)
            # Write CSV for all fields
            with (out_dir / "field_accuracy.csv").open("w", newline="", encoding="utf-8") as w:
                writer = csv.writer(w)
                writer.writerow(["field", "count", "accuracy"])
                for k, cnt, acc in field_acc:
                    writer.writerow([k, cnt, acc])
            # Plot top 15
            top = field_acc[:15]
            if top:
                plt.figure(figsize=(9,4))
                plt.bar([t[0] for t in top], [t[2] for t in top])
                plt.xticks(rotation=45, ha="right")
                plt.ylim(0, 1)
                plt.title("Accuracy by field (top 15)")
                plt.tight_layout()
                plt.savefig(out_dir / "field_accuracy_top15.png", dpi=150)
                plt.close()

        # Accuracy vs citation bins
        if citation_points:
            cits = [c for c, _ in citation_points]
            # Correlation (Spearman) if available
            corr = None
            if np is not None and stats is not None and len(cits) >= 3:
                try:
                    xs = np.array([c for c, _ in citation_points], dtype=float)
                    ys = np.array([y for _, y in citation_points], dtype=float)
                    corr, _p = stats.spearmanr(xs, ys)
                except Exception:
                    corr = None

            # Bins: try quantiles, else fixed
            bins = None
            if np is not None and len(cits) >= 20:
                try:
                    qs = np.quantile(np.array(cits, dtype=float), [0, 0.2, 0.4, 0.6, 0.8, 1.0])
                    bins = sorted(set(float(x) for x in qs))
                except Exception:
                    bins = None
            if not bins:
                bins = [0, 5, 10, 50, 100, 500, 1000, float("inf")]

            def bin_label(v: float) -> str:
                for i in range(len(bins) - 1):
                    lo, hi = bins[i], bins[i + 1]
                    if v >= lo and v < hi:
                        return f"[{int(lo)}-{('inf' if math.isinf(hi) else int(hi))})"
                return f">={int(bins[-2])}"

            btot = Counter()
            bcor = Counter()
            for v, y in citation_points:
                b = bin_label(float(v))
                btot[b] += 1
                bcor[b] += int(y)
            bkeys = sorted(btot.keys(), key=lambda k: (float(k.split('-')[0].strip('[') or 0)))
            with (out_dir / "citation_bin_accuracy.csv").open("w", newline="", encoding="utf-8") as w:
                writer = csv.writer(w)
                writer.writerow(["bin", "count", "accuracy"])
                for k in bkeys:
                    cnt = btot[k]
                    acc = (bcor[k] / cnt) if cnt else 0.0
                    writer.writerow([k, cnt, acc])
            plt.figure(figsize=(9,4))
            plt.bar(bkeys, [(bcor[k] / btot[k]) if btot[k] else 0.0 for k in bkeys])
            plt.xticks(rotation=45, ha="right")
            plt.ylim(0, 1)
            title = "Accuracy by citation bin"
            if corr is not None:
                title += f" (Spearman r={corr:.2f})"
            plt.title(title)
            plt.tight_layout()
            plt.savefig(out_dir / "citation_bin_accuracy.png", dpi=150)
            plt.close()


if __name__ == "__main__":
    main()


