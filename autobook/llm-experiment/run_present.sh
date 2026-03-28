#!/bin/bash
# Generate ablation report from analysis.
#
# Usage:
#   ./run_present.sh --experiment stage1
#   ./run_present.sh --experiment stage1 --analysis 20260326_222032

set -e

export DATABASE_URL=sqlite:///:memory:
export PYTHONPATH=../backend:code/present

EXPERIMENT=""
ANALYSIS_TS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        --analysis) ANALYSIS_TS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [ -z "$EXPERIMENT" ]; then
    echo "Usage: ./run_present.sh --experiment <name> [--analysis <timestamp>]"
    exit 1
fi

# Resolve analysis timestamp
if [ -z "$ANALYSIS_TS" ]; then
    ANALYSIS_TS=$(ls -1t "analysis/$EXPERIMENT/" 2>/dev/null | head -1)
    if [ -z "$ANALYSIS_TS" ]; then
        echo "Error: no analyses found in analysis/$EXPERIMENT/"
        exit 1
    fi
    echo "Resolved latest analysis → $ANALYSIS_TS"
fi

ANALYSIS="analysis/$EXPERIMENT/$ANALYSIS_TS/analysis.json"
if [ ! -f "$ANALYSIS" ]; then
    echo "Error: $ANALYSIS not found"
    exit 1
fi

# Create report
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="report/$EXPERIMENT/$TIMESTAMP"

echo "Creating report directory: $REPORT_DIR"
mkdir -p "$(dirname "$REPORT_DIR")"
cp -r report/template "$REPORT_DIR"
mkdir -p "$REPORT_DIR/component"

echo "Generating LaTeX components..."
/opt/anaconda3/bin/uv run python code/present/main.py \
    --analysis "$ANALYSIS" \
    --output "$REPORT_DIR/component"

echo "Compiling LaTeX..."
cd "$REPORT_DIR"
pdflatex -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
pdflatex -interaction=nonstopmode main.tex > /dev/null 2>&1 || true
cd - > /dev/null

if [ -f "$REPORT_DIR/main.pdf" ]; then
    echo ""
    echo "Report compiled:"
    echo "  Analysis: $ANALYSIS"
    echo "  PDF:      $REPORT_DIR/main.pdf"
else
    echo ""
    echo "Warning: PDF compilation may have failed."
    echo "  Dir: $REPORT_DIR"
fi
