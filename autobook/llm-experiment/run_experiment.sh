#!/bin/bash
# Run ablation experiment.
#
# Usage:
#   ./run_experiment.sh --experiment stage1 --variant full_pipeline
#   ./run_experiment.sh --experiment stage1 --variant full_pipeline --tier basic
#   ./run_experiment.sh --experiment stage1 --all --tier basic --runs 5
#   ./run_experiment.sh --experiment stage1 --warmup

set -e

export DATABASE_URL=sqlite:///:memory:
export PYTHONPATH=../backend:code/run:test_cases:.

EXPERIMENT=""
ALL=false
VARIANT=""
TIER=""
RUNS=1
TEST_CASES=()
WARMUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --experiment) EXPERIMENT="$2"; shift 2 ;;
        --all) ALL=true; shift ;;
        --variant) VARIANT="$2"; shift 2 ;;
        --tier) TIER="$2"; shift 2 ;;
        --runs) RUNS="$2"; shift 2 ;;
        --test-case) TEST_CASES+=("$2"); shift 2 ;;
        --warmup) WARMUP=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [ -z "$EXPERIMENT" ]; then
    echo "Usage: ./run_experiment.sh --experiment <name> --variant <name> [--tier <tier>] [--runs N]"
    exit 1
fi

RUN_BASE="--experiment $EXPERIMENT"

# Warmup only
if [ "$WARMUP" = true ] && [ -z "$VARIANT" ] && [ "$ALL" = false ]; then
    /opt/anaconda3/bin/uv run --extra agent python code/run/main.py $RUN_BASE --warmup
    exit 0
fi

# Build args for a single variant
run_variant() {
    local v="$1"
    RUN_ARGS="$RUN_BASE --variant $v --runs $RUNS"
    [ -n "$TIER" ] && RUN_ARGS="$RUN_ARGS --tier $TIER"
    for tc in "${TEST_CASES[@]}"; do
        RUN_ARGS="$RUN_ARGS --test-case $tc"
    done
    /opt/anaconda3/bin/uv run --extra agent python code/run/main.py $RUN_ARGS
}

# Warmup before first run if requested
if [ "$WARMUP" = true ]; then
    /opt/anaconda3/bin/uv run --extra agent python code/run/main.py $RUN_BASE --warmup
fi

if [ "$ALL" = true ]; then
    for v in single_agent baseline with_correction with_evaluation with_disambiguation full_pipeline; do
        echo ""
        echo "============================================"
        echo "  Variant: $v"
        echo "============================================"
        run_variant "$v"
    done
elif [ -n "$VARIANT" ]; then
    run_variant "$VARIANT"
else
    echo "Usage: ./run_experiment.sh --experiment <name> --variant <name> | --all"
fi
