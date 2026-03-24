"""Experiment analysis — aggregate and compare variant results.

Usage:
    python -m llm_experiment.analysis --results results/stage1/
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from metrics import VariantMetrics


def _load_results(results_dir: Path) -> dict[str, list[dict]]:
    """Load all variant JSON results from directory."""
    results = {}
    for f in sorted(results_dir.glob("*.json")):
        variant_name = f.stem
        data = json.loads(f.read_text())
        results[variant_name] = data
    return results


def aggregate_variant(variant_name: str, test_cases: list[dict]) -> VariantMetrics:
    """Aggregate per-test-case metrics into per-variant summary."""
    n = len(test_cases)
    if n == 0:
        return VariantMetrics(variant_name=variant_name)

    exact_matches = sum(
        1 for tc in test_cases
        if tc.get("debit_tuple_exact_match") and tc.get("credit_tuple_exact_match")
    )
    valid_entries = sum(1 for tc in test_cases if tc.get("entry_valid"))
    errors = sum(1 for tc in test_cases if tc.get("error"))
    fixes_attempted = sum(1 for tc in test_cases if tc.get("fix_attempted"))
    fixes_succeeded = sum(1 for tc in test_cases if tc.get("fix_succeeded"))

    total_cost = sum(tc.get("total_cost_usd", 0) for tc in test_cases)
    mean_latency = sum(tc.get("total_latency_ms", 0) for tc in test_cases) / n

    mean_debit_acc = sum(tc.get("debit_tuple_slot_accuracy", 0) for tc in test_cases) / n
    mean_credit_acc = sum(tc.get("credit_tuple_slot_accuracy", 0) for tc in test_cases) / n
    mean_slot = (mean_debit_acc + mean_credit_acc) / 2

    return VariantMetrics(
        variant_name=variant_name,
        num_test_cases=n,
        exact_match_rate=exact_matches / n,
        mean_slot_accuracy=mean_slot,
        entry_valid_rate=valid_entries / n,
        total_cost_usd=total_cost,
        cost_per_correct_entry=total_cost / exact_matches if exact_matches else float("inf"),
        mean_latency_ms=mean_latency,
        fix_rate=fixes_attempted / n if fixes_attempted else 0.0,
        fix_success_rate=fixes_succeeded / fixes_attempted if fixes_attempted else 0.0,
        error_rate=errors / n,
    )


def print_variant_table(variants: dict[str, VariantMetrics]) -> None:
    """Print per-variant comparison table."""
    print("\n" + "=" * 90)
    print("VARIANT COMPARISON")
    print("=" * 90)
    header = f"{'Variant':<25} {'Match%':>7} {'SlotAcc':>8} {'Valid%':>7} {'Cost$':>8} {'$/Correct':>10} {'LatencyMs':>10} {'Fix%':>6} {'Err%':>6}"
    print(header)
    print("-" * 90)

    for name, m in variants.items():
        print(
            f"{name:<25} "
            f"{m.exact_match_rate*100:>6.1f}% "
            f"{m.mean_slot_accuracy*100:>7.1f}% "
            f"{m.entry_valid_rate*100:>6.1f}% "
            f"${m.total_cost_usd:>7.4f} "
            f"${m.cost_per_correct_entry:>9.4f} "
            f"{m.mean_latency_ms:>9.0f} "
            f"{m.fix_rate*100:>5.1f}% "
            f"{m.error_rate*100:>5.1f}%"
        )
    print("=" * 90)


def print_test_case_breakdown(all_results: dict[str, list[dict]]) -> None:
    """Print per-test-case breakdown across variants."""
    print("\n" + "=" * 90)
    print("PER-TEST-CASE BREAKDOWN")
    print("=" * 90)

    # Collect all test case IDs
    all_ids = set()
    for cases in all_results.values():
        for tc in cases:
            all_ids.add(tc["test_case_id"])

    for tc_id in sorted(all_ids):
        print(f"\n  {tc_id}:")
        for variant, cases in all_results.items():
            tc = next((c for c in cases if c["test_case_id"] == tc_id), None)
            if tc:
                d = "✓" if tc.get("debit_tuple_exact_match") else "✗"
                c = "✓" if tc.get("credit_tuple_exact_match") else "✗"
                err = f" ERROR: {tc['error']}" if tc.get("error") else ""
                print(f"    {variant:<25} D={d} C={c} ${tc.get('total_cost_usd', 0):.4f} {tc.get('total_latency_ms', 0)}ms{err}")


def export_csv(all_results: dict[str, list[dict]], out_path: Path) -> None:
    """Export all results to CSV."""
    rows = []
    for variant, cases in all_results.items():
        for tc in cases:
            tc["variant"] = variant
            rows.append(tc)

    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV exported to {out_path}")


def print_single_variant_detail(variant_name: str, test_cases: list[dict]) -> None:
    """Print detailed report for a single variant."""
    m = aggregate_variant(variant_name, test_cases)

    print(f"\n{'=' * 70}")
    print(f"  {variant_name} — {m.num_test_cases} test cases")
    print(f"{'=' * 70}")
    print(f"  Exact match rate:     {m.exact_match_rate*100:.1f}%")
    print(f"  Mean slot accuracy:   {m.mean_slot_accuracy*100:.1f}%")
    print(f"  Entry valid rate:     {m.entry_valid_rate*100:.1f}%")
    print(f"  Total cost:           ${m.total_cost_usd:.4f}")
    print(f"  Cost per correct:     ${m.cost_per_correct_entry:.4f}")
    print(f"  Mean latency:         {m.mean_latency_ms:.0f}ms")
    print(f"  Fix rate:             {m.fix_rate*100:.1f}%")
    print(f"  Fix success rate:     {m.fix_success_rate*100:.1f}%")
    print(f"  Error rate:           {m.error_rate*100:.1f}%")
    print(f"{'-' * 70}")

    for tc in test_cases:
        d = "✓" if tc.get("debit_tuple_exact_match") else "✗"
        c = "✓" if tc.get("credit_tuple_exact_match") else "✗"
        err = f"  ERROR: {tc['error']}" if tc.get("error") else ""
        print(f"  {tc['test_case_id']:<35} D={d} C={c} "
              f"${tc.get('total_cost_usd', 0):.4f} "
              f"{tc.get('total_latency_ms', 0)}ms{err}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(description="Analyze experiment results")
    parser.add_argument("--results", required=True, help="Results directory")
    parser.add_argument("--variant", default=None, help="Analyze single variant only")
    args = parser.parse_args()

    results_dir = Path(args.results)
    if not results_dir.exists():
        print(f"Directory not found: {results_dir}")
        sys.exit(1)

    all_results = _load_results(results_dir)
    if not all_results:
        print("No result files found")
        sys.exit(1)

    if args.variant:
        # Single variant detail
        if args.variant not in all_results:
            print(f"Variant not found: {args.variant}")
            print(f"Available: {list(all_results.keys())}")
            sys.exit(1)
        print_single_variant_detail(args.variant, all_results[args.variant])
    else:
        # All variants comparison
        variants = {name: aggregate_variant(name, cases) for name, cases in all_results.items()}
        print_variant_table(variants)
        print_test_case_breakdown(all_results)
        csv_path = results_dir / "comparison.csv"
        export_csv(all_results, csv_path)


if __name__ == "__main__":
    main()
