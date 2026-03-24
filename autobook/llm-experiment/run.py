"""Experiment runner — execute test cases in parallel, collect 3-level metrics.

Usage:
    python run.py --variant full_pipeline
    python run.py --variant full_pipeline --test-case 04_sell_inventory
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from rich.console import Console
from rich.live import Live
from rich.table import Table

from services.agent.graph.state import NOT_RUN, AGENT_NAMES
from accounting_engine.validators import validate_journal_entry

from test_cases import TEST_CASES, TestCase
from variants import VARIANTS
from metrics import (
    AgentMetrics, CommonResult, TestCaseMetrics, PerNodeUsageCallback,
)

console = Console()

# ── Sonnet pricing (per million tokens) ───────────────────────────────────
_INPUT_RATE = 3.00 / 1_000_000
_OUTPUT_RATE = 15.00 / 1_000_000
_CACHE_READ_RATE = 0.30 / 1_000_000
_CACHE_WRITE_RATE = 3.75 / 1_000_000


def _build_initial_state(test_case: TestCase) -> dict:
    """Build PipelineState from test case."""
    state: dict = {
        "transaction_text": test_case.transaction_text,
        "user_context": test_case.user_context,
        "ml_enrichment": None,
        "iteration": 0,
    }
    for name in AGENT_NAMES:
        state[f"output_{name}"] = []
        state[f"status_{name}"] = NOT_RUN
        state[f"fix_context_{name}"] = []
        state[f"rag_cache_{name}"] = []
    state["embedding_transaction"] = None
    state["embedding_error"] = None
    state["embedding_rejection"] = None
    state["route"] = "error"
    return state


def _compute_agent_cost(usage: dict) -> float:
    """Compute USD cost from usage_metadata dict."""
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    details = usage.get("input_token_details", {})
    cache_read = details.get("cache_read", 0)
    cache_creation = details.get("cache_creation", 0)
    uncached = input_tokens - cache_read - cache_creation
    return (
        uncached * _INPUT_RATE
        + cache_read * _CACHE_READ_RATE
        + cache_creation * _CACHE_WRITE_RATE
        + output_tokens * _OUTPUT_RATE
    )


def _extract_common_result(state: dict, variant_name: str,
                           callback: PerNodeUsageCallback,
                           elapsed_ms: int) -> CommonResult:
    """Extract standardized result from final state."""
    i = state["iteration"]

    debit_out = state.get("output_debit_corrector", [])
    credit_out = state.get("output_credit_corrector", [])
    debit_tuple = tuple(debit_out[i]["tuple"]) if i < len(debit_out) and debit_out[i] else None
    credit_tuple = tuple(credit_out[i]["tuple"]) if i < len(credit_out) and credit_out[i] else None

    entry_out = state.get("output_entry_builder", [])
    journal_entry = entry_out[i] if i < len(entry_out) else None

    total_input = sum(u.get("input_tokens", 0) for u in callback.usage_by_node.values())
    total_output = sum(u.get("output_tokens", 0) for u in callback.usage_by_node.values())
    total_cost = sum(_compute_agent_cost(u) for u in callback.usage_by_node.values())

    return CommonResult(
        debit_tuple=debit_tuple,
        credit_tuple=credit_tuple,
        journal_entry=journal_entry,
        total_cost_usd=total_cost,
        total_latency_ms=elapsed_ms,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        final_decision=state.get("route", "error"),
    )


def _compute_slot_accuracy(actual: tuple | None, expected: tuple) -> float:
    if actual is None:
        return 0.0
    return sum(1 for a, e in zip(actual, expected) if a == e) / 6


def _extract_test_case_metrics(state: dict, test_case: TestCase,
                                variant_name: str, common: CommonResult,
                                callback: PerNodeUsageCallback) -> TestCaseMetrics:
    """Extract full test case metrics from final state."""
    i = state["iteration"]
    m = TestCaseMetrics(
        test_case_id=test_case.id,
        variant_name=variant_name,
        common=common,
    )

    m.debit_tuple_exact_match = common.debit_tuple == test_case.expected_debit_tuple
    m.credit_tuple_exact_match = common.credit_tuple == test_case.expected_credit_tuple
    m.debit_tuple_slot_accuracy = _compute_slot_accuracy(common.debit_tuple, test_case.expected_debit_tuple)
    m.credit_tuple_slot_accuracy = _compute_slot_accuracy(common.credit_tuple, test_case.expected_credit_tuple)

    if common.journal_entry:
        validation = validate_journal_entry(common.journal_entry)
        m.entry_valid = validation["valid"]
        m.entry_balance_correct = validation["valid"]
    else:
        m.entry_valid = test_case.expected_debit_tuple == (0, 0, 0, 0, 0, 0)

    m.iteration_count = i + 1

    approver_out = state.get("output_approver", [])
    if approver_out and i < len(approver_out):
        m.approver_confidence = approver_out[i].get("confidence")

    if i > 0:
        m.fix_attempted = True
        m.fix_succeeded = approver_out[i].get("approved", False) if i < len(approver_out) else False

        debit_out = state.get("output_debit_corrector", [])
        credit_out = state.get("output_credit_corrector", [])
        if len(debit_out) > 1:
            m.pre_fix_debit_tuple = tuple(debit_out[0]["tuple"]) if debit_out[0] else None
            m.post_fix_debit_tuple = tuple(debit_out[1]["tuple"]) if debit_out[1] else None
        if len(credit_out) > 1:
            m.pre_fix_credit_tuple = tuple(credit_out[0]["tuple"]) if credit_out[0] else None
            m.post_fix_credit_tuple = tuple(credit_out[1]["tuple"]) if credit_out[1] else None

        diag_out = state.get("output_diagnostician", [])
        if diag_out:
            diag = diag_out[0]
            m.diagnostician_decision = diag.get("decision")
            m.fix_root_cause_agent = [p["agent"] for p in diag.get("fix_plans", [])]
            m.rejection_reason = approver_out[0].get("reason") if approver_out else None

    for node_name, usage in callback.usage_by_node.items():
        agent_out = state.get(f"output_{node_name}", [])
        latest = agent_out[i] if i < len(agent_out) else None
        m.agent_metrics[node_name] = AgentMetrics(
            agent_name=node_name,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("input_token_details", {}).get("cache_read", 0),
            cache_write_tokens=usage.get("input_token_details", {}).get("cache_creation", 0),
            cost_usd=_compute_agent_cost(usage),
            output=latest,
            reason=latest.get("reason") if isinstance(latest, dict) else None,
        )

    return m


# ── Status tracking for live display ──────────────────────────────────────

STATUS_PENDING = "⏳ pending"
STATUS_RUNNING = "🔄 running..."
STATUS_DONE = "✅"
STATUS_ERROR = "❌"


_NOTE_WIDTH = 50
_NOTE_TRUNCATE = int(_NOTE_WIDTH * 0.8)

def _build_table(variant_name: str, statuses: dict[str, str]) -> Table:
    """Build a rich table showing current status of all test cases."""
    table = Table(title=f"Variant: {variant_name}", show_lines=False)
    table.add_column("Test Case", style="cyan", width=35)
    table.add_column("Status", width=15)
    table.add_column("D", width=3)
    table.add_column("C", width=3)
    table.add_column("Cost", width=10)
    table.add_column("Latency", width=10)
    table.add_column("Note", width=_NOTE_WIDTH, no_wrap=True)

    for tc_id, info in statuses.items():
        if isinstance(info, str):
            table.add_row(tc_id, info, "", "", "", "", "")
        else:
            status, d, c, cost, latency, note = info
            # Truncate note to 80% of column width
            if len(note) > _NOTE_TRUNCATE:
                note = note[:_NOTE_TRUNCATE] + "…"
            table.add_row(tc_id, status, d, c, cost, latency, note)

    return table


# ── Async runner ──────────────────────────────────────────────────────────

_CONCURRENCY = asyncio.Semaphore(3)  # max 3 test cases at a time

async def _run_one(app, tc: TestCase, config_dict: dict,
                   variant_name: str, statuses: dict) -> TestCaseMetrics:
    """Run a single test case asynchronously (concurrency limited by semaphore)."""
    async with _CONCURRENCY:
        statuses[tc.id] = STATUS_RUNNING

        callback = PerNodeUsageCallback()
        config = {
            "configurable": config_dict or {},
            "callbacks": [callback],
        }
        state = _build_initial_state(tc)

        try:
            start = time.perf_counter()
            final_state = await app.ainvoke(state, config=config)
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            common = _extract_common_result(final_state, variant_name, callback, elapsed_ms)
            metrics = _extract_test_case_metrics(final_state, tc, variant_name, common, callback)

            d = "✓" if metrics.debit_tuple_exact_match else "✗"
            c = "✓" if metrics.credit_tuple_exact_match else "✗"
            statuses[tc.id] = (f"{STATUS_DONE} done", d, c, f"${common.total_cost_usd:.4f}", f"{elapsed_ms}ms", "")
            return metrics

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            statuses[tc.id] = (f"{STATUS_ERROR} failed", "", "", "", f"{elapsed_ms}ms", str(e))
            return TestCaseMetrics(
                test_case_id=tc.id,
                variant_name=variant_name,
                error=str(e),
            )


async def run_variant_async(variant_name: str, test_cases: list[TestCase]) -> list[TestCaseMetrics]:
    """Run all test cases in parallel with live progress display."""
    if variant_name == "single_agent":
        from single_agent.graph import app
    else:
        from services.agent.graph.graph import app

    config_dict = VARIANTS.get(variant_name)
    if config_dict is None and variant_name != "single_agent":
        raise ValueError(f"Unknown variant: {variant_name}")

    # Initialize statuses
    statuses: dict[str, str | tuple] = {tc.id: STATUS_PENDING for tc in test_cases}

    # Run all test cases in parallel with live display
    with Live(_build_table(variant_name, statuses), console=console, refresh_per_second=2) as live:
        tasks = [
            _run_one(app, tc, config_dict, variant_name, statuses)
            for tc in test_cases
        ]

        results = []
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            live.update(_build_table(variant_name, statuses))

    return results


# ── Save results ──────────────────────────────────────────────────────────

def _save_results(results: list[TestCaseMetrics], variant_name: str) -> Path:
    """Save results to JSON — timestamped + latest symlink."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    out_dir = Path("results/stage1")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Timestamped file
    out_path = out_dir / f"{variant_name}_{timestamp}.json"
    # Latest symlink (always points to most recent run)
    latest_path = out_dir / f"{variant_name}.json"

    data = []
    for m in results:
        def _serialize(v):
            if isinstance(v, tuple):
                return list(v)
            return v

        d = {
            "test_case_id": m.test_case_id,
            "variant_name": m.variant_name,
            "debit_tuple_exact_match": m.debit_tuple_exact_match,
            "credit_tuple_exact_match": m.credit_tuple_exact_match,
            "debit_tuple_slot_accuracy": m.debit_tuple_slot_accuracy,
            "credit_tuple_slot_accuracy": m.credit_tuple_slot_accuracy,
            "entry_valid": m.entry_valid,
            "debit_tuple": _serialize(m.common.debit_tuple),
            "credit_tuple": _serialize(m.common.credit_tuple),
            "journal_entry": m.common.journal_entry,
            "total_cost_usd": m.common.total_cost_usd,
            "total_latency_ms": m.common.total_latency_ms,
            "total_input_tokens": m.common.total_input_tokens,
            "total_output_tokens": m.common.total_output_tokens,
            "iteration_count": m.iteration_count,
            "final_decision": m.common.final_decision,
            "fix_attempted": m.fix_attempted,
            "fix_succeeded": m.fix_succeeded,
            "agent_outputs": {
                name: {
                    "output": am.output,
                    "reason": am.reason,
                    "input_tokens": am.input_tokens,
                    "output_tokens": am.output_tokens,
                    "cost_usd": am.cost_usd,
                }
                for name, am in m.agent_metrics.items()
            },
            "pre_fix_debit_tuple": _serialize(m.pre_fix_debit_tuple),
            "post_fix_debit_tuple": _serialize(m.post_fix_debit_tuple),
            "pre_fix_credit_tuple": _serialize(m.pre_fix_credit_tuple),
            "post_fix_credit_tuple": _serialize(m.post_fix_credit_tuple),
            "fix_root_cause_agent": m.fix_root_cause_agent,
            "rejection_reason": m.rejection_reason,
            "diagnostician_decision": m.diagnostician_decision,
            "error": m.error,
        }
        data.append(d)

    json_str = json.dumps(data, indent=2, default=str)
    out_path.write_text(json_str)
    # Update latest symlink
    if latest_path.is_symlink() or latest_path.exists():
        latest_path.unlink()
    latest_path.symlink_to(out_path.name)
    console.print(f"\nResults saved to [bold]{out_path}[/bold]")
    console.print(f"Latest: [bold]{latest_path}[/bold] → {out_path.name}")
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run ablation experiment")
    parser.add_argument("--variant", required=True, choices=list(VARIANTS.keys()))
    parser.add_argument("--test-case", default=None, help="Run single test case by ID")
    args = parser.parse_args()

    cases = TEST_CASES
    if args.test_case:
        cases = [tc for tc in TEST_CASES if tc.id == args.test_case]
        if not cases:
            console.print(f"[red]Test case not found: {args.test_case}[/red]")
            sys.exit(1)

    console.print(f"\n[bold]Running variant: {args.variant}[/bold] ({len(cases)} test cases)\n")
    results = asyncio.run(run_variant_async(args.variant, cases))
    _save_results(results, args.variant)

    # Error details
    failed = [m for m in results if m.error]
    if failed:
        console.print(f"\n[bold red]Errors ({len(failed)}):[/bold red]")
        for m in failed:
            console.print(f"  [red]{m.test_case_id}[/red]: {m.error}")

    # Summary
    exact = sum(1 for m in results if m.debit_tuple_exact_match and m.credit_tuple_exact_match)
    total_cost = sum(m.common.total_cost_usd for m in results)
    console.print(f"\n[bold]Exact match:[/bold] {exact}/{len(results)} ({exact/len(results)*100:.0f}%)")
    console.print(f"[bold]Total cost:[/bold] ${total_cost:.4f}")
    console.print(f"[bold]Errors:[/bold] {len(failed)}")


if __name__ == "__main__":
    main()
