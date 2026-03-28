"""Dashboard summary — top-line numbers and key findings."""
from __future__ import annotations

from formatters import fmt_pct, fmt_cost, fmt_ms, esc


def gen_summary(data: dict) -> str:
    """Top-line dashboard: best variant per metric, key numbers."""
    variants = data["variants"]
    if not variants:
        return "% No variant data.\n"

    # Find best variant per metric
    best_dec = max(variants.items(), key=lambda x: x[1].get("decision_accuracy", 0))
    best_tuple = max(variants.items(), key=lambda x: x[1].get("tuple_match_rate", 0))
    best_entry = max(variants.items(), key=lambda x: x[1].get("entry_match_rate", 0))
    cheapest = min(variants.items(), key=lambda x: x[1]["total_cost_usd"])
    cpc_items = [(n, m) for n, m in variants.items() if m.get("cost_per_correct_entry")]
    best_cpc = min(cpc_items, key=lambda x: x[1]["cost_per_correct_entry"]) if cpc_items else None
    fastest = min(variants.items(), key=lambda x: x[1]["p50_latency_ms"])

    rows = [
        f"  Best decision accuracy & {esc(best_dec[0])} & {fmt_pct(best_dec[1].get('decision_accuracy'))} \\\\",
        f"  Best tuple match & {esc(best_tuple[0])} & {fmt_pct(best_tuple[1].get('tuple_match_rate'))} \\\\",
        f"  Best entry match & {esc(best_entry[0])} & {fmt_pct(best_entry[1].get('entry_match_rate'))} \\\\",
        f"  Lowest cost & {esc(cheapest[0])} & {fmt_cost(cheapest[1]['total_cost_usd'])} \\\\",
        f"  Lowest p50 latency & {esc(fastest[0])} & {fmt_ms(fastest[1]['p50_latency_ms'])}ms \\\\",
    ]
    if best_cpc:
        rows.append(f"  Best cost-of-pass & {esc(best_cpc[0])} & {fmt_cost(best_cpc[1]['cost_per_correct_entry'])} \\\\")

    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Dashboard Summary}\n\\label{tab:summary}\n"
        "\\begin{tabular}{l l r}\n\\toprule\n"
        "Metric & Best Variant & Value \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def gen_failure_analysis(data: dict) -> str:
    """Which test cases did variants disagree on?"""
    per_tc = data["per_test_case"]
    vnames = data["variant_names"]
    if not vnames:
        return "% No data.\n"

    # Find cases where variants disagree
    disagree_rows = []
    all_fail_rows = []
    for tc_id, tc_data in per_tc.items():
        ambig = tc_data.get("ambiguous", False)
        results = {}
        for v in vnames:
            vd = tc_data.get(v)
            if vd is None or vd.get("error"):
                results[v] = None
            elif ambig:
                results[v] = vd.get("decision_correct", False)
            else:
                results[v] = vd.get("entry_match", False)

        valid = {k: v for k, v in results.items() if v is not None}
        if not valid:
            continue

        vals = list(valid.values())
        if all(v is False for v in vals):
            winners = "none"
            all_fail_rows.append(f"  {esc(tc_id)} & {tc_data.get('tier', '')} & {winners} \\\\")
        elif not all(v == vals[0] for v in vals):
            winners = ", ".join(esc(k) for k, v in valid.items() if v)
            losers = ", ".join(esc(k) for k, v in valid.items() if not v)
            disagree_rows.append(f"  {esc(tc_id)} & {tc_data.get('tier', '')} & {winners} & {losers} \\\\")

    parts = []
    if disagree_rows:
        parts.append(
            "\\begin{table}[htbp]\n\\centering\n"
            "\\caption{Variant Disagreements}\n\\label{tab:disagreements}\n"
            "\\resizebox{\\textwidth}{!}{%\n"
            "\\begin{tabular}{l l l l}\n\\toprule\n"
            "Test Case & Tier & Correct & Incorrect \\\\\n"
            "\\midrule\n" + "\n".join(disagree_rows) + "\n\\bottomrule\n"
            "\\end{tabular}}\\end{table}\n"
        )
    if all_fail_rows:
        parts.append(
            "\\begin{table}[htbp]\n\\centering\n"
            "\\caption{Universal Failures (all variants wrong)}\n\\label{tab:all-fail}\n"
            "\\begin{tabular}{l l l}\n\\toprule\n"
            "Test Case & Tier & Correct \\\\\n"
            "\\midrule\n" + "\n".join(all_fail_rows) + "\n\\bottomrule\n"
            "\\end{tabular}\n\\end{table}\n"
        )
    if not parts:
        return "% No disagreements or universal failures.\n"
    return "\n".join(parts)
