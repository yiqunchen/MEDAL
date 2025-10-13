# MEDAL: Medical Evidence Discrepancy Assessment with LLMs

[![Security](https://img.shields.io/badge/security-reviewed-green.svg)](SECURITY.md)

MEDAL evaluates how Large Language Models (LLMs) assess clinical evidence and reconcile discrepancies between observational studies and randomized clinical trials (RCTs).

We use a multi-source dataset of clinical Q&A derived from Cochrane systematic reviews and clinical guidelines. The curated QA dataset, processing scripts, and evaluation code are available at https://anonymous.4open.science/r/llm-evidence-qa-DB-review/

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd MEDAL

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Keys

**CRITICAL: Never commit API keys to git!**

```bash
# Copy the environment template
cp ENV.sample .env

# Edit .env and add your API keys
# .env is already gitignored and will never be committed
nano .env  # or use your preferred editor
```

Required keys:
- `OPENAI_API_KEY` - For GPT-4o, GPT-5, GPT-4o-mini evaluations
- `OPENROUTER_API_KEY` - For Claude Sonnet 4.5 and DeepSeek evaluations

See [SECURITY.md](SECURITY.md) for detailed security guidelines.

### 3. Run Complete Pipeline

```bash
# Run the complete end-to-end analysis
./run_complete_medal_pipeline.sh
```

This will:
1. Validate your environment and API keys
2. Run model evaluations (GPT-4o, Claude Sonnet 4.5, DeepSeek)
3. Perform error analysis and compute metrics
4. Generate visualizations and comparison plots

---

## Repository Structure

```
MEDAL/
├── run_complete_medal_pipeline.sh  # Master pipeline script
├── scripts/                        # Core analysis scripts
│   ├── evaluate_openrouter.py     # Evaluate using OpenRouter (Claude, DeepSeek)
│   ├── evaluate.py                # Evaluate using OpenAI API
│   ├── batch_prepare.py           # Prepare batch evaluation jobs
│   ├── batch_submit.py            # Submit and monitor batch jobs
│   ├── batch_parse_outputs.py     # Parse batch results
│   ├── analyze_errors.py          # Error distribution analysis
│   ├── compute_model_concordance.py
│   ├── plot_confusion_heatmaps.py
│   └── plot_model_comparison.py
├── data/                          # Data directory (gitignored)
│   ├── processed/                 # Processed QA datasets
│   └── runs/                      # Model evaluation outputs
├── analysis/                      # Analysis outputs (gitignored)
├── figures/                       # Generated plots (gitignored)
├── archive/                       # Legacy code and paper drafts
│   ├── notebooks/                 # Exploratory notebooks
│   ├── one_off/                   # One-off analysis scripts
│   ├── paper_drafts/             # Paper abstracts and drafts
│   └── documentation/            # Historical documentation
├── ENV.sample                     # Environment template
├── SECURITY.md                    # Security guidelines
└── README.md                      # This file
```

---

## Pipeline Components

### Data Preparation

Input datasets should be in JSONL format with the following schema:

```jsonl
{"doi": "...", "question": "...", "answer": "Yes|No|No Evidence", "evidence-quality": "High|Moderate|Low|Very Low|Missing", "discrepancy": "Yes|No|Missing", "notes": "..."}
```

### Model Evaluation

#### OpenRouter Models (Claude Sonnet 4.5, DeepSeek)

```bash
# Evaluate using Claude Sonnet 4.5
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-json data/runs/claude_sonnet_45_eval.json \
  --model anthropic/claude-sonnet-4.5 \
  --max-concurrent 15

# Evaluate using DeepSeek
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-json data/runs/deepseek_eval.json \
  --model deepseek/deepseek-chat \
  --max-concurrent 15
```

#### OpenAI Batch API (GPT-4o, GPT-5)

```bash
# 1. Prepare batch input
python3 scripts/batch_prepare.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-jsonl data/processed/qa_batch.jsonl \
  --model gpt-4o \
  --response-format-json

# 2. Submit batch job
python3 scripts/batch_submit.py \
  --input-jsonl data/processed/qa_batch.jsonl \
  --display-name "MEDAL QA Evaluation"

# 3. Parse results (after batch completes)
python3 scripts/batch_parse_outputs.py \
  --input-jsonl data/processed/qa.jsonl \
  --batch-results-jsonl data/runs/<batch_id>.results.jsonl \
  --out-pred-jsonl data/runs/<batch_id>.predictions.jsonl \
  --out-merged-jsonl data/runs/<batch_id>.merged.jsonl
```

### Analysis

```bash
# Error distribution analysis
python3 scripts/analyze_errors.py \
  --merged-jsonl data/runs/<batch_id>.merged.jsonl \
  --out-dir analysis/results/<batch_id>

# Model concordance analysis
python3 scripts/compute_model_concordance.py

# Generate confusion matrices
python3 scripts/plot_confusion_heatmaps.py

# Model comparison plots
python3 scripts/plot_model_comparison.py
```

---

## Data Sources

- **Cochrane Systematic Reviews**: https://www.cochranelibrary.com/
  - Local artifacts: `files-for-regeneration/clean_pubmed_abstract_data_no_protocol.pkl`
- **Clinical Guidelines (AHA)**: https://professional.heart.org/en/guidelines-and-statements/
  - Local artifacts: `guideline-aha/aha_guideline_evidence_cleaned.csv`
- **Curated QA Dataset**: https://anonymous.4open.science/r/llm-evidence-qa-DB-review/

---

## Security

**Critical Security Requirements:**

1. Never commit API keys to version control
2. Always use `.env` for credentials (already gitignored)
3. Use environment variables in all scripts
4. Check for exposed keys before committing

See [SECURITY.md](SECURITY.md) for:
- API key management best practices
- Git history cleanup procedures
- Pre-commit hook setup
- Security vulnerability reporting

---

## Features

- **Checkpointing**: Evaluations save progress every 50 questions
- **Resume Support**: Interrupted evaluations can be resumed
- **High Concurrency**: Configurable concurrent API requests
- **Error Handling**: Graceful error recovery and logging
- **Batch Processing**: Support for OpenAI Batch API
- **Multi-Model**: Evaluate GPT-4o, GPT-5, Claude Sonnet 4.5, DeepSeek

---

## Common Workflows

### Evaluate a New Model

```bash
# 1. Set up API key in .env
echo "NEW_MODEL_API_KEY=your-key" >> .env

# 2. Run evaluation
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-json data/runs/new_model_eval.json \
  --model provider/model-name

# 3. Analyze results
python3 scripts/analyze_errors.py \
  --merged-jsonl data/runs/new_model_eval.json \
  --out-dir analysis/new_model
```

### Compare Multiple Models

```bash
# After running evaluations for multiple models
python3 scripts/compute_model_concordance.py
python3 scripts/plot_model_comparison.py
```

### Generate Negation Dataset

```bash
python3 scripts/negate_dataset.py \
  --input-jsonl data/processed/qa.jsonl \
  --out-jsonl data/processed/qa_negated.jsonl \
  --model gpt-4o-mini \
  --max-concurrent 5
```

---

## Troubleshooting

### API Key Errors

```bash
# Check if .env is loaded
source .env
echo $OPENAI_API_KEY

# Verify .env is not committed
git status .env  # Should show "Untracked files" or not listed
```

### Rate Limiting

```bash
# Reduce concurrent requests
python3 scripts/evaluate_openrouter.py ... --max-concurrent 5
```

### Exposed Keys in Git History

If you accidentally committed API keys, see [SECURITY.md](SECURITY.md#4-git-history-cleanup-if-keys-were-already-committed) for cleanup procedures.

---

## Contributing

1. Never commit API keys or credentials
2. Run security checks before committing:
   ```bash
   grep -r "sk-proj-\|sk-or-v1-\|sk-ant-" . --include="*.py" --include="*.sh"
   ```
3. Use pre-commit hooks (see SECURITY.md)
4. Update documentation for new features

---

## Citation

If you use MEDAL in your research, please cite:

```bibtex
@article{medal2025,
  title={MEDAL: Medical Evidence Discrepancy Assessment with LLMs},
  author={...},
  journal={...},
  year={2025}
}
```

---

## License

[Add license information here]

---

## Support

For issues or questions:
- Open an issue on GitHub
- Check [SECURITY.md](SECURITY.md) for security-related concerns
- Review documentation in `archive/documentation/`
