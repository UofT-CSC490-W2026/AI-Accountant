#!/bin/bash
# Compute all metrics from experiment results, save as JSON.
#
# Usage:
#   ./run_analysis.sh --experiment stage1
#   ./run_analysis.sh --experiment stage1 --variant full_pipeline --variant baseline

set -e

export DATABASE_URL=sqlite:///:memory:
export PYTHONPATH=../backend:code/analysis

if [ $# -eq 0 ]; then
    echo "Usage: ./run_analysis.sh --experiment <name> [--variant <name> ...]"
    exit 1
fi

/opt/anaconda3/bin/uv run --extra agent python code/analysis/main.py "$@"
