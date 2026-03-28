"""Aggregate per-test-case metrics into per-variant summary."""
from __future__ import annotations


def _get_cost(tc: dict) -> float:
    return tc.get("raw_cost_usd", tc.get("total_cost_usd", 0))


def _get_tier(tc: dict) -> str:
    if "tier" in tc:
        return tc["tier"]
    tc_id = tc.get("test_case_id", "")
    if tc_id.startswith("hard_"):
        return "hard"
    if tc_id.startswith("int_"):
        return "intermediate"
    return "basic"


def _get_cache_tokens(tc: dict) -> tuple[int, int]:
    cr, cw = 0, 0
    for am in (tc.get("agent_metrics") or {}).values():
        cr += am.get("cache_read_tokens", 0)
        cw += am.get("cache_write_tokens", 0)
    return cr, cw


def _safe_div(a, b, default=0.0):
    return a / b if b else default


def _safe_inf(v):
    return None if v == float("inf") else v


def aggregate_variant(variant_name: str, test_cases: list[dict]) -> dict:
    """Aggregate per-test-case metrics into per-variant summary dict."""
    n = len(test_cases)
    if n == 0:
        return {"variant_name": variant_name, "num_test_cases": 0}

    non_ambig = [tc for tc in test_cases if not tc.get("ambiguous")]
    ambig = [tc for tc in test_cases if tc.get("ambiguous")]

    exact = sum(1 for tc in non_ambig
                if tc.get("debit_tuple_exact_match") and tc.get("credit_tuple_exact_match"))
    entry_matches = sum(1 for tc in non_ambig if tc.get("entry_match"))
    entry_tax_relaxed = sum(1 for tc in non_ambig if tc.get("entry_tax_relaxed_match"))
    valid = sum(1 for tc in test_cases if tc.get("entry_valid"))
    errors = sum(1 for tc in test_cases if tc.get("error"))
    fixes_a = sum(1 for tc in test_cases if tc.get("fix_attempted"))
    fixes_s = sum(1 for tc in test_cases if tc.get("fix_succeeded"))
    dec_ok = sum(1 for tc in test_cases if tc.get("decision_correct"))
    dec_ok_non_ambig = sum(1 for tc in non_ambig if tc.get("decision_correct"))
    dec_ok_ambig = sum(1 for tc in ambig if tc.get("decision_correct"))
    clar_ok = sum(1 for tc in ambig if tc.get("clarification_correct"))
    n_non_ambig = len(non_ambig)
    n_ambig = len(ambig)

    total_cost = sum(_get_cost(tc) for tc in test_cases)
    actual_cost = sum(tc.get("actual_cost_usd", 0) for tc in test_cases)
    latencies = sorted(tc.get("total_latency_ms", 0) for tc in test_cases)

    d_acc = sum(tc.get("debit_tuple_slot_accuracy", 0) for tc in non_ambig) / n_non_ambig if n_non_ambig else 0
    c_acc = sum(tc.get("credit_tuple_slot_accuracy", 0) for tc in non_ambig) / n_non_ambig if n_non_ambig else 0

    t_in = sum(tc.get("total_input_tokens", 0) for tc in test_cases)
    t_out = sum(tc.get("total_output_tokens", 0) for tc in test_cases)
    t_cr = sum(_get_cache_tokens(tc)[0] for tc in test_cases)
    t_cw = sum(_get_cache_tokens(tc)[1] for tc in test_cases)

    return {
        "variant_name": variant_name, "num_test_cases": n,
        "num_non_ambiguous": n_non_ambig, "num_ambiguous": n_ambig,
        "exact_matches": exact, "entry_matches": entry_matches,
        "entry_tax_relaxed_matches": entry_tax_relaxed,
        "tuple_match_rate": _safe_div(exact, n_non_ambig),
        "entry_match_rate": _safe_div(entry_matches, n_non_ambig),
        "entry_tax_relaxed_rate": _safe_div(entry_tax_relaxed, n_non_ambig),
        "mean_slot_accuracy": (d_acc + c_acc) / 2,
        "entry_valid_rate": valid / n,
        "decision_accuracy": dec_ok / n,
        "decision_accuracy_non_ambig": _safe_div(dec_ok_non_ambig, n_non_ambig),
        "decision_accuracy_ambig": _safe_div(dec_ok_ambig, n_ambig),
        "clarification_correct": clar_ok,
        "clarification_accuracy": _safe_div(clar_ok, n_ambig),
        "total_cost_usd": total_cost,
        "actual_cost_usd": actual_cost,
        "cost_per_correct_entry": _safe_inf(_safe_div(total_cost, exact, float("inf"))),
        "mean_latency_ms": sum(latencies) / n,
        "p50_latency_ms": latencies[n // 2], "p95_latency_ms": latencies[int(n * 0.95)],
        "fix_rate": _safe_div(fixes_a, n),
        "fix_success_rate": _safe_div(fixes_s, fixes_a),
        "error_rate": errors / n,
        "total_input_tokens": t_in, "total_output_tokens": t_out,
        "total_cache_read": t_cr, "total_cache_write": t_cw,
        "cache_hit_rate": _safe_div(t_cr, t_in + t_cr),
        "token_efficiency_ratio": _safe_div(t_out, t_in + t_out),
        "tokens_per_correct_entry": _safe_inf(_safe_div(t_in + t_out, exact, float("inf"))),
    }
