.PHONY: help venv install env gen refine negate eval batch_prepare batch_submit batch_parse analyze

# Config
PY ?= python
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

# Data locations (override as needed)
INPUT_PKL ?= data/intermediate/clean_pubmed_abstract_data_no_protocol.pkl
QA_JSONL ?= data/processed/qa.jsonl
REFINED_JSONL ?= data/processed/qa_refined.jsonl
NEGATED_JSONL ?= data/processed/qa_negated.jsonl
EVAL_JSON ?= data/runs/$(shell date +%F)/gpt4o_eval.json
MODEL ?= gpt-4o
MAX_CONC ?= 8

# Batch settings
BATCH_MODEL ?= gpt-4o-mini
BATCH_JSONL ?= data/processed/qa_batch.jsonl
BATCH_OUT_DIR ?= data/runs
# Set BATCH_ID when parsing/analyzing (e.g., make batch_parse BATCH_ID=batch_123)
BATCH_ID ?=

help:
	@echo "Targets:"
	@echo "  venv            - Create virtualenv (.venv)"
	@echo "  install         - Install dependencies into venv"
	@echo "  env             - Copy ENV.sample to .env if missing"
	@echo "  gen             - Generate QA from abstracts -> $(QA_JSONL)"
	@echo "  refine          - Refine QA -> $(REFINED_JSONL)"
	@echo "  negate          - Create negated set -> $(NEGATED_JSONL)"
	@echo "  eval            - Evaluate QA -> $(EVAL_JSON)"
	@echo "  batch_prepare   - Build batch input JSONL -> $(BATCH_JSONL)"
	@echo "  batch_submit    - Submit batch from $(BATCH_JSONL), saves to $(BATCH_OUT_DIR)"
	@echo "  batch_parse     - Parse batch results using BATCH_ID into predictions/merged JSONL"
	@echo "  analyze         - Summarize errors and metrics for BATCH_ID"

venv:
	@test -d $(VENV) || ($(PY) -m venv $(VENV))

install: venv
	$(ACTIVATE) && pip install -U pip && pip install -r requirements.txt

env:
	@test -f .env || cp ENV.sample .env

# Generation
gen:
	$(ACTIVATE) && $(PY) scripts/generate_questions.py \
		--input-pkl $(INPUT_PKL) \
		--out-jsonl $(QA_JSONL) \
		--model $(MODEL) \
		--max-concurrent $(MAX_CONC)

refine:
	$(ACTIVATE) && $(PY) scripts/refine_questions.py \
		--input-jsonl $(QA_JSONL) \
		--out-jsonl $(REFINED_JSONL) \
		--model $(MODEL) \
		--max-concurrent $(MAX_CONC)

negate:
	$(ACTIVATE) && $(PY) scripts/negate_dataset.py \
		--input-jsonl $(QA_JSONL) \
		--out-jsonl $(NEGATED_JSONL) \
		--model gpt-4o-mini \
		--max-concurrent 5

eval:
	$(ACTIVATE) && $(PY) scripts/evaluate.py \
		--input-jsonl $(QA_JSONL) \
		--out-json $(EVAL_JSON) \
		--model $(MODEL) \
		--max-concurrent 5

# Batch pipeline
batch_prepare:
	$(ACTIVATE) && $(PY) scripts/batch_prepare.py \
		--input-jsonl $(QA_JSONL) \
		--out-jsonl $(BATCH_JSONL) \
		--model $(BATCH_MODEL) \
		--response-format-json

batch_submit:
	$(ACTIVATE) && $(PY) scripts/batch_submit.py \
		--input-jsonl $(BATCH_JSONL) \
		--display-name "MEDAL $(BATCH_MODEL)" \
		--out-dir $(BATCH_OUT_DIR)

batch_parse:
	@test -n "$(BATCH_ID)" || (echo "Set BATCH_ID (e.g., make batch_parse BATCH_ID=batch_123)" && exit 1)
	$(ACTIVATE) && $(PY) scripts/batch_parse_outputs.py \
		--input-jsonl $(QA_JSONL) \
		--batch-results-jsonl $(BATCH_OUT_DIR)/$(BATCH_ID).results.jsonl \
		--out-pred-jsonl $(BATCH_OUT_DIR)/$(BATCH_ID).predictions.jsonl \
		--out-merged-jsonl $(BATCH_OUT_DIR)/$(BATCH_ID).merged.jsonl

analyze:
	@test -n "$(BATCH_ID)" || (echo "Set BATCH_ID (e.g., make analyze BATCH_ID=batch_123)" && exit 1)
	$(ACTIVATE) && $(PY) scripts/analyze_errors.py \
		--merged-jsonl $(BATCH_OUT_DIR)/$(BATCH_ID).merged.jsonl \
		--out-dir $(BATCH_OUT_DIR)/$(BATCH_ID)/analysis

