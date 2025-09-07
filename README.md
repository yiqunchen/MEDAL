## MEDAL: Medical Evidence Discrepancy Assessment with LLMs

MEDAL evaluates how LLMs assess clinical evidence and reconcile discrepancies between observational studies and randomized clinical trials (RCTs).

### Quick start
1) Install deps
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
2) Configure secrets/paths
- Copy `ENV.sample` to `.env` and set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and optional `COCHRANE_USERNAME`/`COCHRANE_PASSWORD`.

3) Run with new CLIs in `scripts/`
- Generate questions from abstracts (supports PKL or JSONL), specify model (works with gpt-4o and gpt-5):
```bash
python scripts/generate_questions.py --input-pkl data/intermediate/clean_pubmed_abstract_data_no_protocol.pkl --out-jsonl data/processed/qa.jsonl --model gpt-4o --max-concurrent 8

# or with JSONL source and GPT-5
python scripts/generate_questions.py --input-jsonl data/intermediate/abstracts.jsonl --out-jsonl data/processed/qa_gpt5.jsonl --model gpt-5 --max-concurrent 8
```

- Optional: refine generated QA items with your chosen model (works with gpt-5):
```bash
python scripts/refine_questions.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-jsonl data/processed/qa_refined.jsonl \
  --model gpt-4o --max-concurrent 8

python scripts/refine_questions.py \
  --input-jsonl data/processed/qa_gpt5.jsonl \
  --out-jsonl data/processed/qa_gpt5_refined.jsonl \
  --model gpt-5 --max-concurrent 8
```
- Create negation set:
```bash
python scripts/negate_dataset.py --input-jsonl data/processed/qa.jsonl --out-jsonl data/processed/qa_negated.jsonl --model gpt-4o-mini --max-concurrent 5
```
- Evaluate a dataset:
```bash
python scripts/evaluate.py --input-jsonl data/processed/qa.jsonl --out-json data/runs/$(date +%F)/gpt4o_eval.json --model gpt-4o
```

### Reproducible Batch Inference (GPT-4o-mini and GPT-5)

1) Prepare batch input JSONL from a QAPair JSONL:
```bash
python scripts/batch_prepare.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-jsonl data/processed/qa_batch_gpt4omini.jsonl \
  --model gpt-4o-mini \
  --response-format-json

python scripts/batch_prepare.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-jsonl data/processed/qa_batch_gpt5.jsonl \
  --model gpt-5 \
  --response-format-json
```

2) Submit and monitor batch job (downloads results/errors on completion):
```bash
python scripts/batch_submit.py \
  --input-jsonl data/processed/qa_batch_gpt4omini.jsonl \
  --display-name "MEDAL QA gpt-4o-mini"

python scripts/batch_submit.py \
  --input-jsonl data/processed/qa_batch_gpt5.jsonl \
  --display-name "MEDAL QA gpt-5"
```
Results will be saved under `data/runs/<batch_id>.results.jsonl` (and errors if any).

3) Parse results and merge with ground truth:
```bash
python scripts/batch_parse_outputs.py \
  --input-jsonl data/processed/qa.jsonl \
  --batch-results-jsonl data/runs/<batch_id>.results.jsonl \
  --out-pred-jsonl data/runs/<batch_id>.predictions.jsonl \
  --out-merged-jsonl data/runs/<batch_id>.merged.jsonl
```

4) Analyze error distributions and produce CSV summaries:
```bash
python scripts/analyze_errors.py \
  --merged-jsonl data/runs/<batch_id>.merged.jsonl \
  --out-dir data/runs/<batch_id>/analysis
```

This batch pipeline uses OpenAI Batch (see docs: `https://platform.openai.com/docs/guides/batch`). The JSONL lines are formatted with `custom_id`, `method`, `url`, and `body` targeting `/v1/chat/completions`.

### Repo layout (core)
- `medal/`: small package for config, clients, schemas
- `scripts/`: CLIs for generation, negation, evaluation
- `data/`: put your `raw/`, `processed/`, `runs/` here (gitignored)
- `notebooks/`: exploratory analysis

### Data schema (JSON lines)
- QAPair per line:
```json
{ "doi": "...", "question": "...", "answer": "Yes|No|No Evidence", "evidence-quality": "High|Moderate|Low|Very Low|Missing", "discrepancy": "Yes|No|Missing", "notes": "..." }
```

### Notes
- Old ad-hoc scripts remain but are sanitized to use environment variables and relative paths. Prefer using `scripts/` going forward.