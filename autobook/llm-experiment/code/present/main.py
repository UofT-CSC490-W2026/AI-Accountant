"""Present CLI — generate LaTeX dashboard components from analysis JSON.

Pure rendering — no computation, no merging.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from summary import gen_summary, gen_failure_analysis
from tables import (
    gen_accuracy_non_ambiguous, gen_accuracy_ambiguous,
    gen_cost_accuracy_tradeoff, gen_marginal_deltas, gen_tier_breakdown,
)
from details import (
    gen_token_summary, gen_agent_breakdown,
    gen_per_test_case, gen_consistency,
)

COMPONENTS = [
    ("summary.tex", gen_summary),
    ("accuracy_non_ambiguous.tex", gen_accuracy_non_ambiguous),
    ("accuracy_ambiguous.tex", gen_accuracy_ambiguous),
    ("cost_accuracy.tex", gen_cost_accuracy_tradeoff),
    ("marginal_deltas.tex", gen_marginal_deltas),
    ("tier_breakdown.tex", gen_tier_breakdown),
    ("failure_analysis.tex", gen_failure_analysis),
    ("token_summary.tex", gen_token_summary),
    ("agent_breakdown.tex", gen_agent_breakdown),
    ("per_test_case.tex", gen_per_test_case),
    ("consistency.tex", gen_consistency),
]


def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX dashboard")
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    path = Path(args.analysis)
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text())
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, gen_fn in COMPONENTS:
        content = gen_fn(data)
        (out_dir / filename).write_text(content)
        print(f"  Generated {filename}")

    print(f"\n{len(COMPONENTS)} components written to {out_dir}")


if __name__ == "__main__":
    main()
