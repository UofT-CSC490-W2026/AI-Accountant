"""Serialize TestCaseMetrics to dict and save results to disk."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from models import TestCaseMetrics


def _serialize(v):
    if isinstance(v, tuple):
        return list(v)
    return v


def result_to_dict(m: TestCaseMetrics, model: str) -> dict:
    """Convert a TestCaseMetrics to a JSON-serializable dict."""
    return {
        "test_case_id": m.test_case_id,
        "variant_name": m.variant_name,
        "model": model,
        "debit_tuple_exact_match": m.debit_tuple_exact_match,
        "credit_tuple_exact_match": m.credit_tuple_exact_match,
        "debit_tuple_slot_accuracy": m.debit_tuple_slot_accuracy,
        "credit_tuple_slot_accuracy": m.credit_tuple_slot_accuracy,
        "entry_valid": m.entry_valid,
        "debit_tuple": _serialize(m.common.debit_tuple),
        "credit_tuple": _serialize(m.common.credit_tuple),
        "journal_entry": m.common.journal_entry,
        "actual_cost_usd": m.common.actual_cost_usd,
        "raw_cost_usd": m.common.raw_cost_usd,
        "total_latency_ms": m.common.total_latency_ms,
        "total_input_tokens": m.common.total_input_tokens,
        "total_output_tokens": m.common.total_output_tokens,
        "total_llm_calls": m.common.total_llm_calls,
        "iteration_count": m.iteration_count,
        "final_decision": m.common.final_decision,
        "fix_attempted": m.fix_attempted,
        "fix_succeeded": m.fix_succeeded,
        "agent_metrics": {
            name: {
                "input_tokens": am.input_tokens, "output_tokens": am.output_tokens,
                "cache_read_tokens": am.cache_read_tokens, "cache_write_tokens": am.cache_write_tokens,
                "total_input_tokens": am.total_input_tokens, "llm_calls": am.llm_calls,
                "actual_cost_usd": am.actual_cost_usd, "raw_cost_usd": am.raw_cost_usd,
                "output": am.output, "reason": am.reason,
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
        "validation_error": m.pipeline_state.get("validation_error") if m.pipeline_state else None,
        "decision_correct": m.decision_correct,
        "entry_match": m.entry_match,
        "clarification_correct": m.clarification_correct,
        "clarification_questions": m.clarification_questions,
        "ambiguous": m.ambiguous,
        "tier": m.tier,
        "error": m.error,
        "pipeline_state": m.pipeline_state,
    }


def save_results(results: list[TestCaseMetrics], variant_name: str, model: str,
                  experiment: str = "default") -> Path:
    """Save results to results/<experiment>/<variant>/ (flat, no timestamp subdir)."""
    run_dir = Path("results") / experiment / variant_name
    run_dir.mkdir(parents=True, exist_ok=True)

    for m in results:
        d = result_to_dict(m, model)
        (run_dir / f"{m.test_case_id}.json").write_text(json.dumps(d, indent=2, default=str))

    return run_dir
