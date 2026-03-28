"""LaTeX generators for comparison tables."""
from __future__ import annotations

from formatters import fmt_pct, fmt_cost, fmt_ms, fmt_delta, fmt_tokens, esc


def _cnt(num, denom, rate):
    """Format as '3/5 (60.0%)'."""
    return f"{num}/{denom} ({fmt_pct(rate)})"


def gen_accuracy_non_ambiguous(data: dict) -> str:
    variants = data["variants"]
    rows = []
    for name, m in variants.items():
        nn = m.get("num_non_ambiguous", 0)
        rows.append(
            f"  {esc(name)} & {_cnt(int(m.get('decision_accuracy_non_ambig', 0) * nn), nn, m.get('decision_accuracy_non_ambig'))} "
            f"& {_cnt(m.get('exact_matches', 0), nn, m.get('tuple_match_rate'))} "
            f"& {_cnt(m.get('entry_matches', 0), nn, m.get('entry_match_rate'))} "
            f"& {_cnt(m.get('entry_tax_relaxed_matches', 0), nn, m.get('entry_tax_relaxed_rate'))} \\\\"
        )
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Non-Ambiguous Accuracy}\n\\label{tab:acc-non-ambig}\n"
        "\\begin{tabular}{l rrrr}\n\\toprule\n"
        "Variant & Decision & Tuple & Entry & Entry (tax-relaxed) \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def gen_accuracy_ambiguous(data: dict) -> str:
    variants = data["variants"]
    rows = []
    for name, m in variants.items():
        na = m.get("num_ambiguous", 0)
        dec_ok = int(m.get("decision_accuracy_ambig", 0) * na)
        clar_ok = m.get("clarification_correct", 0)
        rows.append(
            f"  {esc(name)} & {_cnt(dec_ok, na, m.get('decision_accuracy_ambig'))} "
            f"& {_cnt(clar_ok, na, m.get('clarification_accuracy'))} \\\\"
        )
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Ambiguous Accuracy}\n\\label{tab:acc-ambig}\n"
        "\\begin{tabular}{l rr}\n\\toprule\n"
        "Variant & Decision & Clarification \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def gen_cost_accuracy_tradeoff(data: dict) -> str:
    variants = data["variants"]
    rows = []
    for name, m in variants.items():
        n = m["num_test_cases"]
        dec_ok = int(m["decision_accuracy"] * n)
        cpc = fmt_cost(m.get("cost_per_correct_entry"))
        total_tok = m["total_input_tokens"] + m["total_output_tokens"]
        rows.append(
            f"  {esc(name)} & {_cnt(dec_ok, n, m['decision_accuracy'])} "
            f"& {fmt_pct(m.get('entry_match_rate'))} "
            f"& {fmt_tokens(total_tok)} & {fmt_tokens(m.get('total_cache_read', 0))} "
            f"& {fmt_cost(m['total_cost_usd'])} & {fmt_cost(m.get('actual_cost_usd', 0))} "
            f"& {cpc} "
            f"& {fmt_ms(m['p50_latency_ms'])}ms \\\\"
        )
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Cost--Accuracy Tradeoff}\n\\label{tab:cost-accuracy}\n"
        "\\resizebox{\\textwidth}{!}{%\n"
        "\\begin{tabular}{l r r rr rr r r}\n\\toprule\n"
        "Variant & Decision & Entry & Tokens & Cache R "
        "& Raw \\$ & Cached \\$ & \\$/Corr & p50 \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}}\\end{table}\n"
    )


def gen_marginal_deltas(data: dict) -> str:
    deltas = data["marginal_deltas"]
    if not deltas:
        return "% No marginal delta data available.\n"
    rows = []
    for d in deltas:
        ef = esc(d['from'])
        el = esc(d['label'])
        dd = fmt_delta(d['d_decision'])
        dt = fmt_delta(d['d_tuple'])
        de = fmt_delta(d['d_entry'])
        dcl = fmt_delta(d['d_clarification'])
        dc = fmt_delta(d['d_cost_usd'], '\\$')
        dl = fmt_delta(d['d_latency_ms'], 'ms')
        rows.append(f"  {ef} $\\to$ {el} & {dd} & {dt} & {de} & {dcl} & {dc} & {dl} \\\\")
    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Marginal Component Value}\n\\label{tab:marginal-deltas}\n"
        "\\begin{tabular}{l rrrr rr}\n\\toprule\n"
        "Transition & $\\Delta$Dec & $\\Delta$Tuple & $\\Delta$Entry "
        "& $\\Delta$Clar & $\\Delta$Cost & $\\Delta$Latency \\\\\n"
        "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )


def gen_tier_breakdown(data: dict) -> str:
    tiers = ["basic", "intermediate", "hard"]
    vnames = data["variant_names"]
    tb = data["tier_breakdown"]
    header = "Tier & Metric & " + " & ".join(esc(v) for v in vnames) + " \\\\"
    rows = []
    for tier in tiers:
        cells = [tier.capitalize(), "Decision"]
        for v in vnames:
            t = tb.get(v, {}).get(tier)
            if t:
                n = t["n"]
                ok = t["decision_correct"]
                cells.append(f"{ok}/{n}")
            else:
                cells.append("---")
        rows.append("  " + " & ".join(cells) + " \\\\")

        if tier != "hard":
            for metric, k_ok, k_n in [("Tuple", "tuple_matches", "n_non_ambiguous"),
                                       ("Entry", "entry_matches", "n_non_ambiguous")]:
                cells = ["", metric]
                for v in vnames:
                    t = tb.get(v, {}).get(tier)
                    if t:
                        cells.append(f"{t.get(k_ok, 0)}/{t.get(k_n, 0)}")
                    else:
                        cells.append("---")
                rows.append("  " + " & ".join(cells) + " \\\\")
        else:
            cells = ["", "Clarification"]
            for v in vnames:
                t = tb.get(v, {}).get(tier)
                if t:
                    cells.append(f"{t.get('clarification_correct', 0)}/{t.get('n_ambiguous', 0)}")
                else:
                    cells.append("---")
            rows.append("  " + " & ".join(cells) + " \\\\")
        rows.append("  \\midrule")
    rows.pop()

    return (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Accuracy by Difficulty Tier}\n\\label{tab:tier-breakdown}\n"
        f"\\begin{{tabular}}{{ll {'r' * len(vnames)}}}\n\\toprule\n"
        f"{header}\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n"
        "\\end{tabular}\n\\end{table}\n"
    )
