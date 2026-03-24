#!/bin/bash
# Analyze experiment results.
#
# Usage:
#   ./run_analysis.sh --all                          # compare all variants
#   ./run_analysis.sh --variant full_pipeline        # single variant detail

set -e

export DATABASE_URL=sqlite:///:memory:
export PYTHONPATH=../backend

VARIANT=""
ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --all) ALL=true; shift ;;
        --variant) VARIANT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [ "$ALL" = true ]; then
    python analysis.py --results results/stage1/
elif [ -n "$VARIANT" ]; then
    python analysis.py --results results/stage1/ --variant "$VARIANT"
else
    echo "Usage: ./run_analysis.sh --variant <name> | --all"
fi
