"""Experiment runner — CLI entry point."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_AUTOBOOK = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_AUTOBOOK / "backend"))

from rich.console import Console

from test_cases_basic import TEST_CASES as BASIC
from test_cases_intermediate import INTERMEDIATE_TEST_CASES
from test_cases_hard import HARD_TEST_CASES
from test_cases_intermediate_from_hard import INTERMEDIATE_FROM_HARD_TEST_CASES

ALL_CASES = BASIC + INTERMEDIATE_TEST_CASES + HARD_TEST_CASES + INTERMEDIATE_FROM_HARD_TEST_CASES
TIERS = {"basic", "intermediate", "hard"}

from variants.variants import VARIANTS
from pricing import PRICING
from warmup import warmup_caches
from runner import run_variant_async
from serialize import save_results

console = Console()


def _filter_cases(args):
    cases = ALL_CASES
    if args.tier:
        cases = [tc for tc in cases if tc.tier == args.tier]
        if not cases:
            console.print(f"[red]No test cases for tier: {args.tier}[/red]")
            sys.exit(1)
    if args.test_case:
        ids = set(args.test_case)
        cases = [tc for tc in cases if tc.id in ids]
        missing = ids - {tc.id for tc in cases}
        if missing:
            console.print(f"[red]Not found: {', '.join(sorted(missing))}[/red]")
            sys.exit(1)
    return cases


def _print_summary(all_results: list[list], n_cases: int) -> None:
    from rich.table import Table

    flat = [m for run in all_results for m in run]
    n = len(flat)
    if n == 0:
        return

    failed = [m for m in flat if m.error]
    exact = sum(1 for m in flat if m.debit_tuple_exact_match and m.credit_tuple_exact_match)

    t_in = sum(m.common.total_input_tokens for m in flat)
    t_out = sum(m.common.total_output_tokens for m in flat)
    t_cr = sum(
        sum((c.get("input_token_details") or {}).get("cache_read", 0)
            for c in (m.pipeline_state or {}).get("llm_calls", []))
        for m in flat)
    t_cw = sum(
        sum((c.get("input_token_details") or {}).get("cache_creation", 0)
            for c in (m.pipeline_state or {}).get("llm_calls", []))
        for m in flat)

    raw = sum(m.common.raw_cost_usd for m in flat)
    act = sum(m.common.actual_cost_usd for m in flat)
    lat = sum(m.common.total_latency_ms for m in flat)

    err_style = "green" if len(failed) == 0 else "red"
    match_pct = exact / n * 100
    match_style = "green" if match_pct >= 80 else "yellow" if match_pct >= 50 else "red"

    console.print(f"\n[{err_style}]Errors:[/{err_style}]       {len(failed)}")
    console.print(f"[{match_style}]Exact match:[/{match_style}]  {exact}/{n} ({match_pct:.0f}%)")

    # Totals table
    totals = Table(title="Totals", show_lines=False)
    totals.add_column("", width=10)
    totals.add_column("Total", justify="right", width=10)
    totals.add_column("In", justify="right", width=10)
    totals.add_column("Out", justify="right", width=8)
    totals.add_column("Cache R", justify="right", width=10)
    totals.add_column("Cache W", justify="right", width=10)
    totals.add_row("Tokens", f"{t_in+t_out:,}", f"{t_in:,}", f"{t_out:,}", f"{t_cr:,}", f"{t_cw:,}")
    totals.add_row("Cost", "", f"[bold]Raw ${raw:.4f}[/bold]", "", f"[dim]Cached ${act:.4f}[/dim]", "")
    totals.add_row("Latency", f"{lat:,}ms", "", "", "", "")
    console.print(totals)

    # Averages table
    avgs = Table(title="Per-Test Average", show_lines=False)
    avgs.add_column("", width=10)
    avgs.add_column("In", justify="right", width=10)
    avgs.add_column("Out", justify="right", width=8)
    avgs.add_column("Cache R", justify="right", width=10)
    avgs.add_column("Cache W", justify="right", width=10)
    avgs.add_row("Tokens", f"{t_in//n:,}", f"{t_out//n:,}", f"{t_cr//n:,}", f"{t_cw//n:,}")
    avgs.add_row("Cost", f"[bold]Raw ${raw/n:.4f}[/bold]", "", f"[dim]Cached ${act/n:.4f}[/dim]", "")
    avgs.add_row("Latency", f"{lat//n:,}ms", "", "", "")
    console.print(avgs)


def main():
    parser = argparse.ArgumentParser(description="Run ablation experiment")
    parser.add_argument("--experiment", default="default")
    parser.add_argument("--variant", required=False, choices=list(VARIANTS.keys()))
    parser.add_argument("--tier", default=None, choices=sorted(TIERS))
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default="sonnet", choices=list(PRICING.keys()))
    parser.add_argument("--test-case", action="append", default=None)
    parser.add_argument("--warmup", action="store_true")
    args = parser.parse_args()

    pricing = PRICING[args.model]

    if args.warmup:
        warmup_caches()
        if not args.variant:
            return

    if not args.variant:
        console.print("[red]--variant is required (unless using --warmup alone)[/red]")
        sys.exit(1)

    cases = _filter_cases(args)
    tier_label = f" | tier: {args.tier}" if args.tier else ""
    runs_label = f" | runs: {args.runs}" if args.runs > 1 else ""
    console.print(f"\n[bold]{args.experiment}:[/bold] {args.variant}{tier_label}{runs_label} | {args.model} | {len(cases)} cases\n")

    all_results = asyncio.run(run_variant_async(args.variant, cases, pricing, total_runs=args.runs))

    for run_results in all_results:
        save_results(run_results, args.variant, args.model, experiment=args.experiment)

    if [m for run in all_results for m in run if m.error]:
        console.print(f"\n[bold red]Errors:[/bold red]")
        for run in all_results:
            for m in run:
                if m.error:
                    console.print(f"  [red]{m.test_case_id}[/red]: {m.error}")

    _print_summary(all_results, len(cases))

    console.print(f"\n[bold]Results:[/bold]  results/{args.experiment}/{args.variant}/")


if __name__ == "__main__":
    main()
