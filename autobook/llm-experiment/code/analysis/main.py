"""Analysis CLI — compute all metrics, save as JSON.

Usage:
    python main.py --experiment stage1
    python main.py --experiment stage1 --variant full_pipeline --variant baseline
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from load import load_experiment, load_all_multi_runs
from aggregate import aggregate_variant
from breakdowns import (
    compute_tier_breakdown, compute_marginal_deltas,
    compute_per_test_case, compute_agent_breakdown,
    compute_multi_run_consistency,
)


def build_analysis(experiment: str, variants: list[str] | None = None) -> dict:
    all_results = load_experiment(experiment, variants)
    if not all_results:
        return {}
    variant_names = list(all_results.keys())
    all_runs = load_all_multi_runs(experiment, variant_names)
    return {
        "generated_at": datetime.now().isoformat(),
        "experiment": experiment,
        "variant_names": variant_names,
        "variants": {name: aggregate_variant(name, cases) for name, cases in all_results.items()},
        "tier_breakdown": compute_tier_breakdown(all_results),
        "marginal_deltas": compute_marginal_deltas(all_results),
        "per_test_case": compute_per_test_case(all_results),
        "agent_breakdown": compute_agent_breakdown(all_results),
        "multi_run_consistency": compute_multi_run_consistency(all_runs),
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze experiment results")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--variant", action="append", default=None)
    args = parser.parse_args()

    print(f"Experiment: {args.experiment}")
    analysis = build_analysis(args.experiment, args.variant)
    if not analysis:
        print("Error: no results found", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("analysis") / args.experiment / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "analysis.json"
    out_path.write_text(json.dumps(analysis, indent=2, default=str))

    print(f"Variants: {', '.join(analysis['variant_names'])}")
    print(f"Analysis saved to {out_path}")


if __name__ == "__main__":
    main()
