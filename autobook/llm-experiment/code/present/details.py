"""LaTeX generators for detail tables."""
from __future__ import annotations

from formatters import fmt_pct, fmt_cost, fmt_tokens, fmt_ms, esc


def gen_token_summary(data: dict) -> str:
    """Table 7a: Token consumption summary per variant."""
    variants = data["variants"]
    rows = []
    for name, m in variants.items():
        total = m["total_input_tokens"] + m["total_output_tokens"]
        tpc = fmt_tokens(m.get("tokens_per_correct_entry"))
        rows.append(
            f"  {esc(name)} & {fmt_tokens(total)} "
            f"& {fmt_tokens(m['total_input_tokens'])} & {fmt_tokens(m['total_output_tokens'])} "
            f"& {fmt_pct(m.get('cache_hit_rate'))} "
            f"& {fmt_pct(m.get('token_efficiency_ratio'))} & {tpc} \\\\"
        )
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Token Consumption}\n\\label{tab:tokens}\n"
        "\\begin{tabular}{l rrrr rr}\n\\toprule\n"
        "Variant & Total & Input & Output & Cache\\% & TokEff & Tok/Corr \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def gen_agent_breakdown(data: dict) -> str:
    """Table 7b: Per-agent token/cost breakdown per variant."""
    ab = data["agent_breakdown"]
    parts = []
    for variant_name, agents in ab.items():
        if not agents:
            continue
        rows = []
        for name in sorted(agents.keys()):
            a = agents[name]
            rows.append(
                f"  {esc(name)} & {a['llm_calls']} "
                f"& {a['input_tokens']:,} & {a['output_tokens']:,} "
                f"& {a['cache_read_tokens']:,} & {a['cache_write_tokens']:,} "
                f"& {fmt_cost(a['raw_cost_usd'])} & {fmt_cost(a['actual_cost_usd'])} \\\\"
            )
        ev = esc(variant_name)
        vl = variant_name.replace('_', '-')
        parts.append(
            f"\\begin{{table}}[htbp]\n\\centering\n"
            f"\\caption{{Agent Breakdown: {ev}}}\n"
            f"\\label{{tab:agent-{vl}}}\n"
            f"\\begin{{tabular}}{{l r rr rr rr}}\n\\toprule\n"
            f"Agent & Calls & Input & Output & Cache R & Cache W & Raw \\$ & Actual \\$ \\\\\n"
            f"\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
            f"\\end{{tabular}}\n\\end{{table}}\n"
        )
    return "\n".join(parts)


def _format_tc_cell(vd: dict | None, ambiguous: bool) -> str:
    if vd is None:
        return "---"
    if vd.get("error"):
        return "ERR"
    dec = "\\cmark" if vd["decision_correct"] else "\\xmark"
    if ambiguous:
        clar = "\\cmark" if vd.get("clarification_correct") else "\\xmark"
        return f"D:{dec} Cl:{clar}"
    tup_ok = vd.get("debit_match", False) and vd.get("credit_match", False)
    tup = "\\cmark" if tup_ok else "\\xmark"
    ent = "\\cmark" if vd.get("entry_match") else "\\xmark"
    return f"D:{dec} T:{tup} E:{ent}"


def gen_per_test_case(data: dict) -> str:
    """Table 8: Per-test-case — only failures and disagreements with cost."""
    per_tc = data["per_test_case"]
    vnames = data["variant_names"]

    header = "Test Case & Tier & " + " & ".join(esc(v) for v in vnames) + " \\\\"
    rows = []
    for tc_id, tc_data in per_tc.items():
        ambig = tc_data.get("ambiguous", False)

        # Check if any variant failed or variants disagree
        results = []
        for v in vnames:
            vd = tc_data.get(v)
            if vd is None or vd.get("error"):
                results.append(None)
            elif ambig:
                results.append(vd.get("decision_correct", False))
            else:
                results.append(vd.get("entry_match", False))
        valid = [r for r in results if r is not None]
        if valid and all(valid):
            continue  # all pass — skip

        cells = [esc(tc_id), tc_data.get("tier", "")]
        for v in vnames:
            vd = tc_data.get(v)
            cell = _format_tc_cell(vd, ambig)
            if vd and not vd.get("error"):
                cell += f" \\${vd.get('cost_usd', 0):.3f}"
            cells.append(cell)
        rows.append("  " + " & ".join(cells) + " \\\\")

    if not rows:
        return "% All test cases passed across all variants.\n"

    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Failures and Disagreements "
        "(D=Decision, T=Tuple, E=Entry, Cl=Clarification)}\n"
        "\\label{tab:failures}\n"
        "\\resizebox{\\textwidth}{!}{%\n"
        f"\\begin{{tabular}}{{ll {'l' * len(vnames)}}}\n\\toprule\n"
        f"{header}\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}}\\end{table}\n"
    )


def gen_consistency(data: dict) -> str:
    """Table 9: Multi-run consistency."""
    mrc = data["multi_run_consistency"]
    if not mrc:
        return "% No multi-run data available.\n"
    rows = []
    for variant_name, c in mrc.items():
        rows.append(
            f"  {esc(variant_name)} & {c['num_runs']} "
            f"& {c['match_rate_mean']:.1f} $\\pm$ {c['match_rate_std']:.1f} "
            f"& \\${c['cost_mean']:.4f} $\\pm$ \\${c['cost_std']:.4f} "
            f"& {c['latency_mean']:.0f} $\\pm$ {c['latency_std']:.0f} \\\\"
        )
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Multi-Run Consistency ($\\mu \\pm \\sigma$)}\n"
        "\\label{tab:consistency}\n"
        "\\begin{tabular}{l r rrr}\n\\toprule\n"
        "Variant & Runs & Match\\% & Cost \\$ & Latency (ms) \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )
