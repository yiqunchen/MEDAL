#!/bin/bash
# MEDAL Complete Analysis Pipeline
# This script runs the complete end-to-end MEDAL benchmark evaluation and analysis
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found. Please copy ENV.sample to .env and fill in your API keys."
    exit 1
fi

# Load environment variables
source .env

# Check required API keys
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-..." ]; then
    print_error "OPENAI_API_KEY not set in .env file"
    exit 1
fi

if [ -z "$OPENROUTER_API_KEY" ] || [ "$OPENROUTER_API_KEY" = "sk-or-v1-..." ]; then
    print_warning "OPENROUTER_API_KEY not set. Claude Sonnet 4.5 and DeepSeek evaluations will be skipped."
fi

# Create output directories
mkdir -p data/processed
mkdir -p data/runs
mkdir -p analysis/results
mkdir -p figures

print_status "==================================================="
print_status "MEDAL COMPLETE ANALYSIS PIPELINE"
print_status "==================================================="
echo ""

# ===================================================================
# STEP 1: DATA PREPARATION
# ===================================================================
print_status "STEP 1: Data Preparation"
print_status "---------------------------------------------------"

# Check if input data exists
if [ ! -f "data/processed/qa_from_4o.jsonl" ]; then
    print_warning "Primary QA dataset not found at data/processed/qa_from_4o.jsonl"
    print_status "Please ensure your QA data is available before proceeding."
fi

if [ ! -f "data/processed/guideline2_qapairs.jsonl" ]; then
    print_warning "Guideline QA dataset not found at data/processed/guideline2_qapairs.jsonl"
fi

echo ""

# ===================================================================
# STEP 2: MODEL EVALUATIONS
# ===================================================================
print_status "STEP 2: Model Evaluations"
print_status "---------------------------------------------------"

OUTPUT_DIR="data/runs/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

print_status "Output directory: $OUTPUT_DIR"
echo ""

# 2A: OpenRouter Models (Claude Sonnet 4.5, DeepSeek)
if [ ! -z "$OPENROUTER_API_KEY" ] && [ "$OPENROUTER_API_KEY" != "sk-or-v1-..." ]; then
    print_status "2A: Running OpenRouter evaluations (Claude Sonnet 4.5, DeepSeek)"

    if [ -f "scripts/run_openrouter_evals.sh" ]; then
        bash scripts/run_openrouter_evals.sh
    else
        print_warning "scripts/run_openrouter_evals.sh not found. Skipping OpenRouter evaluations."
    fi
    echo ""
else
    print_warning "Skipping OpenRouter evaluations (API key not configured)"
    echo ""
fi

# 2B: GPT-4o Batch Evaluation
print_status "2B: Running GPT-4o batch evaluation"
if [ -f "data/processed/qa_from_4o.jsonl" ]; then
    print_status "Preparing batch input..."
    python3 scripts/batch_prepare.py \
        --input-jsonl data/processed/qa_from_4o.jsonl \
        --out-jsonl "$OUTPUT_DIR/qa_batch_gpt4o.jsonl" \
        --model gpt-4o \
        --response-format-json

    print_status "Submitting batch job..."
    print_status "Note: Monitor batch job completion manually and run batch_parse_outputs.py when complete"
    echo ""
else
    print_warning "Skipping GPT-4o batch evaluation (input data not found)"
    echo ""
fi

# ===================================================================
# STEP 3: ANALYSIS
# ===================================================================
print_status "STEP 3: Running Analysis Scripts"
print_status "---------------------------------------------------"

# 3A: Error Analysis
print_status "3A: Error distribution analysis"
if compgen -G "data/runs/*/merged.jsonl" > /dev/null; then
    for merged_file in data/runs/*/merged.jsonl; do
        batch_id=$(basename $(dirname "$merged_file"))
        print_status "Analyzing $merged_file..."
        python3 scripts/analyze_errors.py \
            --merged-jsonl "$merged_file" \
            --out-dir "analysis/results/$batch_id"
    done
    echo ""
else
    print_warning "No merged result files found. Skipping error analysis."
    echo ""
fi

# 3B: Model Concordance
print_status "3B: Computing model concordance"
if [ -f "scripts/compute_model_concordance.py" ]; then
    python3 scripts/compute_model_concordance.py
    echo ""
else
    print_warning "scripts/compute_model_concordance.py not found"
    echo ""
fi

# 3C: Confusion Matrices
print_status "3C: Generating confusion heatmaps"
if [ -f "scripts/plot_confusion_heatmaps.py" ]; then
    python3 scripts/plot_confusion_heatmaps.py
    echo ""
else
    print_warning "scripts/plot_confusion_heatmaps.py not found"
    echo ""
fi

# 3D: Model Comparison Plots
print_status "3D: Creating model comparison plots"
if [ -f "scripts/plot_model_comparison.py" ]; then
    python3 scripts/plot_model_comparison.py
    echo ""
else
    print_warning "scripts/plot_model_comparison.py not found"
    echo ""
fi

# 3E: Comprehensive Analysis (if available)
print_status "3E: Running comprehensive multi-model analysis"
if [ -f "scripts/run_complete_gpt4o_claude_sonnet_45_deepseek_v3_medal_benchmark_analysis_with_confusion_matrices_citation_year_field_stratification.py" ]; then
    python3 scripts/run_complete_gpt4o_claude_sonnet_45_deepseek_v3_medal_benchmark_analysis_with_confusion_matrices_citation_year_field_stratification.py
    echo ""
fi

# ===================================================================
# STEP 4: SUMMARY
# ===================================================================
print_status "==================================================="
print_status "PIPELINE COMPLETE"
print_status "==================================================="
echo ""
print_status "Results saved to:"
print_status "  - Model outputs:  $OUTPUT_DIR"
print_status "  - Analysis:       analysis/results/"
print_status "  - Figures:        figures/"
echo ""
print_status "Next steps:"
print_status "  1. Review analysis outputs in analysis/results/"
print_status "  2. Check figures/ directory for visualizations"
print_status "  3. If batch jobs are still running, monitor them with:"
print_status "     python3 scripts/batch_submit.py --status"
echo ""
