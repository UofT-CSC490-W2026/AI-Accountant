"""Compute tier, marginal, per-test-case, agent, and consistency breakdowns."""
from __future__ import annotations

import statistics
from collections import defaultdict

from aggregate import aggregate_variant, _get_cost, _get_tier


def compute_tier_breakdown(all_results: dict[str, list[dict]]) -> dict:
    tiers = ["basic", "intermediate", "hard"]
    breakdown = {}
    for variant_name, test_cases in all_results.items():
        vt = {}
        for tier in tiers:
            cases = [tc for tc in test_cases if _get_tier(tc) == tier]
            if not cases:
                continue
            n = len(cases)
            non_ambig = [tc for tc in cases if not tc.get("ambiguous")]
            ambig = [tc for tc in cases if tc.get("ambiguous")]
            exact = sum(1 for tc in non_ambig
                        if tc.get("debit_tuple_exact_match") and tc.get("credit_tuple_exact_match"))
            entry_ok = sum(1 for tc in non_ambig if tc.get("entry_match"))
            entry_tax_ok = sum(1 for tc in non_ambig if tc.get("entry_tax_relaxed_match"))
            dec_ok = sum(1 for tc in cases if tc.get("decision_correct"))
            clar_ok = sum(1 for tc in ambig if tc.get("clarification_correct"))
            vt[tier] = {
                "n": n, "n_non_ambiguous": len(non_ambig), "n_ambiguous": len(ambig),
                "tuple_matches": exact, "tuple_match_rate": exact / len(non_ambig) if non_ambig else 0,
                "entry_matches": entry_ok, "entry_match_rate": entry_ok / len(non_ambig) if non_ambig else 0,
                "entry_tax_relaxed_matches": entry_tax_ok,
                "entry_tax_relaxed_rate": entry_tax_ok / len(non_ambig) if non_ambig else 0,
                "decision_correct": dec_ok, "decision_accuracy": dec_ok / n,
                "clarification_correct": clar_ok, "clarification_accuracy": clar_ok / len(ambig) if ambig else 0,
                "total_cost_usd": sum(_get_cost(tc) for tc in cases),
            }
        breakdown[variant_name] = vt
    return breakdown


def compute_marginal_deltas(all_results: dict[str, list[dict]]) -> list[dict]:
    ladder = [
        ("baseline", "with_correction", "+correction"),
        ("baseline", "with_evaluation", "+evaluation"),
        ("baseline", "with_disambiguation", "+disambiguation"),
        ("with_disambiguation", "full_pipeline", "+correction+evaluation"),
    ]
    deltas = []
    for base_name, target_name, label in ladder:
        if base_name not in all_results or target_name not in all_results:
            continue
        b = aggregate_variant(base_name, all_results[base_name])
        t = aggregate_variant(target_name, all_results[target_name])
        deltas.append({
            "from": base_name, "to": target_name, "label": label,
            "d_decision": t["decision_accuracy"] - b["decision_accuracy"],
            "d_tuple": t["tuple_match_rate"] - b["tuple_match_rate"],
            "d_entry": t["entry_match_rate"] - b["entry_match_rate"],
            "d_clarification": t["clarification_accuracy"] - b["clarification_accuracy"],
            "d_cost_usd": t["total_cost_usd"] - b["total_cost_usd"],
            "d_latency_ms": t["mean_latency_ms"] - b["mean_latency_ms"],
        })
    return deltas


def compute_per_test_case(all_results: dict[str, list[dict]]) -> dict:
    all_ids = set()
    for cases in all_results.values():
        for tc in cases:
            all_ids.add(tc["test_case_id"])
    per_tc = {}
    for tc_id in sorted(all_ids):
        per_tc[tc_id] = {"tier": "basic", "ambiguous": False}
        for variant_name, cases in all_results.items():
            tc = next((c for c in cases if c["test_case_id"] == tc_id), None)
            if tc:
                per_tc[tc_id]["tier"] = _get_tier(tc)
                per_tc[tc_id]["ambiguous"] = tc.get("ambiguous", False)
                per_tc[tc_id][variant_name] = {
                    "debit_match": tc.get("debit_tuple_exact_match", False),
                    "credit_match": tc.get("credit_tuple_exact_match", False),
                    "entry_match": tc.get("entry_match", False),
                    "decision_correct": tc.get("decision_correct", False),
                    "clarification_correct": tc.get("clarification_correct"),
                    "final_decision": tc.get("final_decision"),
                    "ambiguous": tc.get("ambiguous", False),
                    "cost_usd": _get_cost(tc),
                    "latency_ms": tc.get("total_latency_ms", 0),
                    "error": tc.get("error"),
                }
    return per_tc


def compute_agent_breakdown(all_results: dict[str, list[dict]]) -> dict:
    breakdown = {}
    for variant_name, test_cases in all_results.items():
        totals: dict[str, dict] = defaultdict(lambda: {
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "total_input_tokens": 0, "llm_calls": 0,
            "actual_cost_usd": 0.0, "raw_cost_usd": 0.0,
        })
        for tc in test_cases:
            if tc.get("error"):
                continue
            for name, am in (tc.get("agent_metrics") or {}).items():
                t = totals[name]
                for k in ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]:
                    t[k] += am.get(k, 0)
                t["total_input_tokens"] += am.get("total_input_tokens", am.get("input_tokens", 0))
                t["llm_calls"] += am.get("llm_calls", 1)
                t["actual_cost_usd"] += am.get("actual_cost_usd", am.get("cost_usd", 0))
                t["raw_cost_usd"] += am.get("raw_cost_usd", 0)
        breakdown[variant_name] = dict(totals)
    return breakdown


def compute_multi_run_consistency(all_runs: dict[str, list[list[dict]]]) -> dict:
    consistency = {}
    for variant_name, runs in all_runs.items():
        if len(runs) < 2:
            continue
        match_rates, costs, latencies = [], [], []
        for run_cases in runs:
            m = aggregate_variant(variant_name, run_cases)
            match_rates.append(m["tuple_match_rate"] * 100)
            costs.append(m["total_cost_usd"])
            latencies.append(m["mean_latency_ms"])
        n = len(runs)
        consistency[variant_name] = {
            "num_runs": n,
            "match_rate_mean": statistics.mean(match_rates),
            "match_rate_std": statistics.stdev(match_rates) if n > 1 else 0,
            "cost_mean": statistics.mean(costs),
            "cost_std": statistics.stdev(costs) if n > 1 else 0,
            "latency_mean": statistics.mean(latencies),
            "latency_std": statistics.stdev(latencies) if n > 1 else 0,
        }
    return consistency
