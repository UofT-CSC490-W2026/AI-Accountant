"""Build initial pipeline state and extract results from final state."""
from __future__ import annotations

from services.agent.graph.state import NOT_RUN, AGENT_NAMES
from pricing import compute_actual_cost, compute_raw_cost, total_input_tokens
from models import CommonResult
from callback import PerNodeUsageCallback


def build_initial_state(test_case) -> dict:
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
    state["decision"] = None
    state["validation_error"] = None
    return state


def extract_common_result(state: dict, callback: PerNodeUsageCallback,
                          elapsed_ms: int, pricing: dict) -> CommonResult:
    """Extract standardized result from final state."""
    i = state["iteration"]

    from services.agent.utils.parsers.json_output import extract_debit_tuple, extract_credit_tuple

    debit_out = state.get("output_debit_classifier", [])
    credit_out = state.get("output_credit_classifier", [])
    debit_raw = debit_out[i] if i < len(debit_out) and debit_out[i] else None
    credit_raw = credit_out[i] if i < len(credit_out) and credit_out[i] else None
    debit_tuple = tuple(extract_debit_tuple(debit_raw)) if debit_raw else None
    credit_tuple = tuple(extract_credit_tuple(credit_raw)) if credit_raw else None

    entry_out = state.get("output_entry_drafter", [])
    raw_entry = entry_out[i] if i < len(entry_out) else None
    journal_entry = raw_entry

    t_input = sum(total_input_tokens(c) for c in callback.llm_calls)
    t_output = sum(c.get("output_tokens", 0) for c in callback.llm_calls)
    t_actual = sum(compute_actual_cost(c, pricing) for c in callback.llm_calls)
    t_raw = sum(compute_raw_cost(c, pricing) for c in callback.llm_calls)

    return CommonResult(
        debit_tuple=debit_tuple, credit_tuple=credit_tuple,
        journal_entry=journal_entry,
        actual_cost_usd=t_actual, raw_cost_usd=t_raw,
        total_latency_ms=elapsed_ms,
        total_input_tokens=t_input, total_output_tokens=t_output,
        total_llm_calls=len(callback.llm_calls),
        final_decision="validation_failed" if state.get("validation_error") else (state.get("decision") or "error"),
    )


def extract_state_snapshot(state: dict) -> dict:
    """Extract output_*, status_*, fix_context_* for debugging."""
    snapshot = {"iteration": state.get("iteration", 0)}
    for key, val in state.items():
        if key.startswith("output_") or key.startswith("status_") or key.startswith("fix_context_"):
            snapshot[key] = val
    snapshot["decision"] = state.get("decision")
    snapshot["validation_error"] = state.get("validation_error")
    return snapshot
