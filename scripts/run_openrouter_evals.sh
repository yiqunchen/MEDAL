#!/bin/bash
# Run evaluations using OpenRouter for Claude Sonnet 4.5 and DeepSeek

set -e  # Exit on error

# Export OpenRouter API key from environment or .env file
# IMPORTANT: Set OPENROUTER_API_KEY in your .env file or environment
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "ERROR: OPENROUTER_API_KEY environment variable not set"
    echo "Please set it in your .env file or export it:"
    echo "  export OPENROUTER_API_KEY='your-key-here'"
    exit 1
fi
export OPENROUTER_HTTP_REFERER='https://github.com'
export OPENROUTER_X_TITLE='MEDAL Evaluation'

# Input files
ABSTRACTS_JSONL="data/processed/qa_from_4o.jsonl"
GUIDELINES_JSONL="data/processed/guideline2_qapairs.jsonl"

# Output directory
OUTPUT_DIR="data/runs/openrouter_$(date +%Y%m%d)"
mkdir -p "$OUTPUT_DIR"

echo "Starting OpenRouter evaluations..."
echo "Output directory: $OUTPUT_DIR"
echo ""

# ==========================================
# ABSTRACTS DATASET (8,533 questions)
# ==========================================

# Run Claude Sonnet 4.5 evaluation on abstracts
echo "=========================================="
echo "Running Claude Sonnet 4.5 on abstracts..."
echo "=========================================="
python3 scripts/evaluate_openrouter.py \
  --input-jsonl "$ABSTRACTS_JSONL" \
  --out-json "$OUTPUT_DIR/claude_sonnet_45_abstracts_eval.json" \
  --model "anthropic/claude-sonnet-4.5" \
  --max-concurrent 15

echo ""
echo "Claude Sonnet 4.5 abstracts evaluation completed!"
echo ""

# Run DeepSeek evaluation on abstracts
echo "=========================================="
echo "Running DeepSeek on abstracts..."
echo "=========================================="
python3 scripts/evaluate_openrouter.py \
  --input-jsonl "$ABSTRACTS_JSONL" \
  --out-json "$OUTPUT_DIR/deepseek_abstracts_eval.json" \
  --model "deepseek/deepseek-chat" \
  --max-concurrent 15

echo ""
echo "DeepSeek abstracts evaluation completed!"
echo ""

# ==========================================
# GUIDELINES DATASET (10,456 questions)
# ==========================================

# Run Claude Sonnet 4.5 evaluation on guidelines
echo "=========================================="
echo "Running Claude Sonnet 4.5 on guidelines..."
echo "=========================================="
python3 scripts/evaluate_openrouter.py \
  --input-jsonl "$GUIDELINES_JSONL" \
  --out-json "$OUTPUT_DIR/claude_sonnet_45_guidelines_eval.json" \
  --model "anthropic/claude-sonnet-4.5" \
  --max-concurrent 15

echo ""
echo "Claude Sonnet 4.5 guidelines evaluation completed!"
echo ""

# Run DeepSeek evaluation on guidelines
echo "=========================================="
echo "Running DeepSeek on guidelines..."
echo "=========================================="
python3 scripts/evaluate_openrouter.py \
  --input-jsonl "$GUIDELINES_JSONL" \
  --out-json "$OUTPUT_DIR/deepseek_guidelines_eval.json" \
  --model "deepseek/deepseek-chat" \
  --max-concurrent 15

echo ""
echo "DeepSeek guidelines evaluation completed!"
echo ""

# ==========================================
# RESULTS SUMMARY
# ==========================================
echo "=========================================="
echo "All evaluations completed!"
echo "=========================================="
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "Abstracts dataset (8,533 questions):"
echo "  - Claude Sonnet 4.5: $OUTPUT_DIR/claude_sonnet_45_abstracts_eval.json"
echo "  - DeepSeek:          $OUTPUT_DIR/deepseek_abstracts_eval.json"
echo ""
echo "Guidelines dataset (10,456 questions):"
echo "  - Claude Sonnet 4.5: $OUTPUT_DIR/claude_sonnet_45_guidelines_eval.json"
echo "  - DeepSeek:          $OUTPUT_DIR/deepseek_guidelines_eval.json"
echo ""
echo "To analyze results, you can use:"
echo "  python3 scripts/analyze_errors.py --merged-jsonl <results-file> --out-dir <output-dir>"
