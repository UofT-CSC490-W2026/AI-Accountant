#!/bin/bash
# Run ablation experiment.
#
# Usage:
#   ./run_experiment.sh --variant full_pipeline
#   ./run_experiment.sh --variant full_pipeline --test-case 12_pay_salaries
#   ./run_experiment.sh --all

set -e

export DATABASE_URL=sqlite:///:memory:
export PYTHONPATH=../backend

ALL=false
VARIANT=""
TEST_CASE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --all) ALL=true; shift ;;
        --variant) VARIANT="$2"; shift 2 ;;
        --test-case) TEST_CASE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [ "$ALL" = true ]; then
    for v in single_agent classify_and_build with_correction with_evaluation full_pipeline; do
        echo ""
        echo "============================================"
        echo "  Variant: $v"
        echo "============================================"
        python run.py --variant "$v"
    done
elif [ -n "$VARIANT" ]; then
    RUN_ARGS="--variant $VARIANT"
    [ -n "$TEST_CASE" ] && RUN_ARGS="$RUN_ARGS --test-case $TEST_CASE"
    python run.py $RUN_ARGS
else
    echo "Usage: ./run_experiment.sh --variant <name> | --all"
fi
