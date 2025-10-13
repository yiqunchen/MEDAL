# OpenRouter Evaluation Setup

This document describes how to run evaluations using OpenRouter for Claude Sonnet 4.5 and DeepSeek models.

## Summary of Current Results

### Existing Results
- **GPT-5**: Full evaluation completed on 8,533 questions
  - Results in `data/runs/batch-gpt5-answers.jsonl` and `data/runs/gpt5_run/`
  - Overall accuracy: 0.678 (67.8%)
  - Context experiments completed on 500-item subset

### Missing Results
- **Claude 4/Claude Sonnet 4.5**: No existing results found
- **DeepSeek**: No existing results found
- **Other open-weight models**: Not yet evaluated

## New Evaluation Script

I've created `scripts/evaluate_openrouter.py` which supports:
- Claude Sonnet 4.5 (`anthropic/claude-sonnet-4.5`)
- DeepSeek (`deepseek/deepseek-chat`)
- Any other OpenRouter-supported model

### Available OpenRouter Models

#### Claude Models
- `anthropic/claude-sonnet-4.5` - Latest Sonnet model (recommended)
- `anthropic/claude-sonnet-4` - Claude Sonnet 4
- `anthropic/claude-3.7-sonnet` - Claude 3.7 Sonnet
- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet

#### DeepSeek Models
- `deepseek/deepseek-chat` - DeepSeek V3.2 in non-thinking mode (recommended)
- `deepseek/deepseek-r1` - DeepSeek reasoning model
- `deepseek/deepseek-chat-v3.1` - DeepSeek V3.1

## Running Evaluations

### Option 1: Run All Evaluations (Recommended)

```bash
# This will run both Claude Sonnet 4.5 and DeepSeek on BOTH datasets
# - Abstracts dataset (8,533 questions)
# - Guidelines dataset (10,456 questions)
# Total: ~19,000 questions across both models
./scripts/run_openrouter_evals.sh
```

Results will be saved to `data/runs/openrouter_YYYYMMDD/`:
- `claude_sonnet_45_abstracts_eval.json`
- `deepseek_abstracts_eval.json`
- `claude_sonnet_45_guidelines_eval.json`
- `deepseek_guidelines_eval.json`

### Option 2: Run Individual Models

```bash
# Set the API key (replace with your actual key)
export OPENROUTER_API_KEY='your-openrouter-api-key-here'

# Run Claude Sonnet 4.5
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa_from_4o.jsonl \
  --out-json data/runs/claude_sonnet_45_eval.json \
  --model anthropic/claude-sonnet-4.5 \
  --max-concurrent 5

# Run DeepSeek
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa_from_4o.jsonl \
  --out-json data/runs/deepseek_eval.json \
  --model deepseek/deepseek-chat \
  --max-concurrent 5

# Test with a small sample first
python3 scripts/evaluate_openrouter.py \
  --input-jsonl data/processed/qa_from_4o.jsonl \
  --out-json data/runs/test_output.json \
  --model anthropic/claude-sonnet-4.5 \
  --max-concurrent 3 \
  --limit 10
```

### Parameters

- `--input-jsonl`: Path to the input QA dataset (JSONL format)
- `--out-json`: Path to save results (JSON format)
- `--model`: OpenRouter model ID
- `--max-concurrent`: Number of concurrent API requests (default: 15)
- `--limit`: Optional limit for testing (evaluates only first N questions)

### Features

✅ **Progress Bar**: Real-time progress tracking with tqdm
✅ **Checkpointing**: Automatically saves progress every 50 questions
✅ **Resume on Interrupt**: Can safely Ctrl+C and resume from checkpoint
✅ **High Concurrency**: Default 15 concurrent requests for fast evaluation
✅ **Error Handling**: Gracefully handles API errors and continues

## Expected Runtime

**Per dataset, per model:**
- **Abstracts** (8,533 questions with `--max-concurrent 15`): ~15-20 minutes
- **Guidelines** (10,456 questions with `--max-concurrent 15`): ~20-25 minutes

**Total for complete run** (both datasets, both models):
- ~2-3 hours for all 4 evaluations
- Can run in parallel by opening multiple terminals if desired

**Test run** (10 questions):
- ~30 seconds

## Cost Estimation

OpenRouter pricing (approximate as of 2025):
- **Claude Sonnet 4.5**: ~$3-5 per 1M tokens
- **DeepSeek**: ~$0.14-0.27 per 1M tokens (much cheaper!)

For 8,533 questions (~500 tokens each = 4.2M tokens):
- Claude Sonnet 4.5: ~$15-20
- DeepSeek: ~$1-2

## Output Format

Results are saved as JSON with this structure:

```json
{
  "0": {
    "doi": "10.1002/14651858.CD008285",
    "question": "Does chemoradiotherapy improve 5-year survival rates...",
    "model_answer": "Yes",
    "model_evidence-quality": "High",
    "model_discrepancy": "No",
    "model_notes": "Multiple randomized controlled trials...",
    "ground_truth_answer": "Yes",
    "ground_truth_evidence-quality": "High",
    "ground_truth_discrepancy": "No"
  },
  ...
}
```

The script automatically calculates and prints accuracy at the end.

## Analyzing Results

Once you have results, you can use the existing analysis scripts:

```bash
# Analyze errors (this may need adaptation for the new format)
python3 scripts/analyze_errors.py \
  --merged-jsonl data/runs/openrouter_*/claude_sonnet_45_eval.json \
  --out-dir data/runs/openrouter_*/analysis
```

## Checkpointing & Resuming

The script automatically saves checkpoints every 50 completed questions. If interrupted:

1. **Checkpoint files** are saved as `<output_filename>.checkpoint.json`
2. **To resume**: Simply re-run the same command - it will automatically detect and load the checkpoint
3. **On completion**: Checkpoint files are automatically deleted

Example:
```bash
# Start evaluation
python3 scripts/evaluate_openrouter.py --input-jsonl data/processed/qa_from_4o.jsonl --out-json data/runs/results.json --model anthropic/claude-sonnet-4.5

# Press Ctrl+C to interrupt
^C

# Resume from checkpoint - same command
python3 scripts/evaluate_openrouter.py --input-jsonl data/processed/qa_from_4o.jsonl --out-json data/runs/results.json --model anthropic/claude-sonnet-4.5
# Output: "Resuming from checkpoint: 150 already completed"
```

## Troubleshooting

1. **API Key Error**: Make sure `OPENROUTER_API_KEY` is set in your environment:
   ```bash
   export OPENROUTER_API_KEY='your-key-here'
   # Or it should be in ~/.bash_profile
   ```

2. **Rate Limiting**: If you hit rate limits, reduce `--max-concurrent`:
   ```bash
   python3 scripts/evaluate_openrouter.py ... --max-concurrent 5
   ```

3. **JSON Parsing Errors**: The script handles markdown-wrapped JSON responses automatically

4. **Progress bar not showing**: Make sure `tqdm` is installed:
   ```bash
   pip install tqdm
   ```

## Next Steps

After running the evaluations:

1. **Compare with GPT-5**: Load the GPT-5 results and compare accuracy scores
2. **Analyze by domain**: Break down performance by medical specialty
3. **Update paper abstract**: Include Claude and DeepSeek results alongside GPT-5
4. **Run context experiments**: Adapt the context evaluation for Claude/DeepSeek if needed

## Fixed Issues

- ✅ Fixed `~/.bash_profile` error (removed invalid `$gcc` line)
- ✅ Created OpenRouter evaluation script with JSON parsing
- ✅ Tested successfully with Claude Sonnet 4.5 (67% accuracy on 3-question test)
- ✅ Added support for DeepSeek models
