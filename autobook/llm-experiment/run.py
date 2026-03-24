"""Experiment runner — execute test cases against a variant, collect 3-level metrics.

Usage:
    python -m llm_experiment.run --variant full_pipeline
    python -m llm_experiment.run --variant full_pipeline --test-case 04_sell_inventory
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from services.agent.graph.state import NOT_RUN, AGENT_NAMES
from accounting_engine.validators import validate_journal_entry

from test_cases import TEST_CASES, TestCase
from variants import VARIANTS
from metrics import (
    AgentMetrics, CommonResult, TestCaseMetrics, PerNodeUsageCallback,
)


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
    # Initialize all per-agent fields as empty
    for name in AGENT_NAMES:
        state[f"output_{name}"] = []
        state[f"status_{name}"] = NOT_RUN
        state[f"fix_context_{name}"] = []
        state[f"rag_cache_{name}"] = []
    # Embedding cache
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

    # Final tuples — read from corrector output (passthrough copies classifier if needed)
    debit_out = state.get("output_debit_corrector", [])
    credit_out = state.get("output_credit_corrector", [])
    debit_tuple = tuple(debit_out[i]["tuple"]) if i < len(debit_out) and debit_out[i] else None
    credit_tuple = tuple(credit_out[i]["tuple"]) if i < len(credit_out) and credit_out[i] else None

    # Journal entry
    entry_out = state.get("output_entry_builder", [])
    journal_entry = entry_out[i] if i < len(entry_out) else None

    # Total tokens from callback
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
    """Fraction of 6 tuple slots that match."""
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

    # ── Accuracy ──────────────────────────────────────────────────
    m.debit_tuple_exact_match = common.debit_tuple == test_case.expected_debit_tuple
    m.credit_tuple_exact_match = common.credit_tuple == test_case.expected_credit_tuple
    m.debit_tuple_slot_accuracy = _compute_slot_accuracy(common.debit_tuple, test_case.expected_debit_tuple)
    m.credit_tuple_slot_accuracy = _compute_slot_accuracy(common.credit_tuple, test_case.expected_credit_tuple)

    if common.journal_entry:
        validation = validate_journal_entry(common.journal_entry)
        m.entry_valid = validation["valid"]
        m.entry_balance_correct = validation["valid"]  # balance is part of validation
    else:
        # No entry — valid only if expected tuples are all zeros
        m.entry_valid = test_case.expected_debit_tuple == (0, 0, 0, 0, 0, 0)

    # ── Pipeline ──────────────────────────────────────────────────
    m.iteration_count = i + 1

    approver_out = state.get("output_approver", [])
    if approver_out and i < len(approver_out):
        m.approver_confidence = approver_out[i].get("confidence")

    # ── Fix loop ──────────────────────────────────────────────────
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

    # ── Per-agent metrics ─────────────────────────────────────────
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


def run_variant(variant_name: str, test_cases: list[TestCase]) -> list[TestCaseMetrics]:
    """Run all test cases against a variant, return metrics."""
    # Load graph
    if variant_name == "single_agent":
        from single_agent.graph import app
    else:
        from services.agent.graph.graph import app

    # Build config
    config_dict = VARIANTS.get(variant_name)
    if config_dict is None and variant_name != "single_agent":
        raise ValueError(f"Unknown variant: {variant_name}")

    results: list[TestCaseMetrics] = []

    for tc in test_cases:
        print(f"  Running {tc.id}...", end=" ", flush=True)
        callback = PerNodeUsageCallback()
        config = {
            "configurable": config_dict or {},
            "callbacks": [callback],
        }
        state = _build_initial_state(tc)

        try:
            start = time.perf_counter()
            final_state = app.invoke(state, config=config)
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            common = _extract_common_result(final_state, variant_name, callback, elapsed_ms)
            metrics = _extract_test_case_metrics(final_state, tc, variant_name, common, callback)
            print(f"D={'✓' if metrics.debit_tuple_exact_match else '✗'} "
                  f"C={'✓' if metrics.credit_tuple_exact_match else '✗'} "
                  f"${common.total_cost_usd:.4f} {elapsed_ms}ms")
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            metrics = TestCaseMetrics(
                test_case_id=tc.id,
                variant_name=variant_name,
                error=str(e),
            )
            print(f"ERROR: {e}")

        results.append(metrics)

    return results


def _save_results(results: list[TestCaseMetrics], variant_name: str) -> Path:
    """Save results to JSON."""
    out_dir = Path("results/stage1")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{variant_name}.json"

    data = []
    for m in results:
        d = {
            "test_case_id": m.test_case_id,
            "variant_name": m.variant_name,
            "debit_tuple_exact_match": m.debit_tuple_exact_match,
            "credit_tuple_exact_match": m.credit_tuple_exact_match,
            "debit_tuple_slot_accuracy": m.debit_tuple_slot_accuracy,
            "credit_tuple_slot_accuracy": m.credit_tuple_slot_accuracy,
            "entry_valid": m.entry_valid,
            "iteration_count": m.iteration_count,
            "total_cost_usd": m.common.total_cost_usd,
            "total_latency_ms": m.common.total_latency_ms,
            "total_input_tokens": m.common.total_input_tokens,
            "total_output_tokens": m.common.total_output_tokens,
            "final_decision": m.common.final_decision,
            "fix_attempted": m.fix_attempted,
            "fix_succeeded": m.fix_succeeded,
            "error": m.error,
        }
        data.append(d)

    out_path.write_text(json.dumps(data, indent=2))
    print(f"\nResults saved to {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Run ablation experiment")
    parser.add_argument("--variant", required=True, choices=list(VARIANTS.keys()))
    parser.add_argument("--test-case", default=None, help="Run single test case by ID")
    args = parser.parse_args()

    cases = TEST_CASES
    if args.test_case:
        cases = [tc for tc in TEST_CASES if tc.id == args.test_case]
        if not cases:
            print(f"Test case not found: {args.test_case}")
            sys.exit(1)

    print(f"Running variant: {args.variant} ({len(cases)} test cases)")
    results = run_variant(args.variant, cases)
    _save_results(results, args.variant)

    # Quick summary
    exact = sum(1 for m in results if m.debit_tuple_exact_match and m.credit_tuple_exact_match)
    total_cost = sum(m.common.total_cost_usd for m in results)
    errors = sum(1 for m in results if m.error)
    print(f"\nExact match: {exact}/{len(results)} ({exact/len(results)*100:.0f}%)")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
