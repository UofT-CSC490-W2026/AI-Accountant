"""Produce tool: generate report-ready assets from processed results.

Usage:
    python -m a4.p4.scripts.produce --processed a4/p4/results/processed.json --output-dir a4/p4/results/assets
    python -m a4.p4.scripts.produce --processed a4/p4/results/processed.json --wandb-dir a4/p4/results/collected/wandb --output-dir a4/p4/results/assets

Input:
    --processed: structured JSON from process.py (runs, per_problem, comparisons)
    --wandb-dir: directory of per-run W&B JSONs from collect.py (for F3, F4, F5)

Output (per design-assets.md):
    Tables: T1 (summary), T2 (gained/lost), T3 (synergy), T4 (errors), T5 (ablation) — LaTeX .tex files
    Figures: F1-F8 — PDF files
    Macros: p4_macros.tex — \newcommand definitions for all key numbers
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Constants from design-assets.md
# ---------------------------------------------------------------------------

RUN_ORDER = [
    "baseline", "separate_a", "separate_b", "combined_ab",
    "separate_c", "separate_d", "separate_e",
    "combined_cd", "combined_cde", "combined_all",
]
RUN_LABELS = {
    "baseline": "Baseline",
    "separate_a": "+ A",
    "separate_b": "+ B",
    "combined_ab": "+ A+B",
    "separate_c": "+ C",
    "separate_d": "+ D",
    "separate_e": "+ E",
    "combined_cd": "+ C+D",
    "combined_cde": "+ C+D+E",
    "combined_all": "Comb.\\ All",
}
# Labels with reward descriptions (for tables that need them)
RUN_LABELS_LONG = {
    "baseline": "Baseline",
    "separate_a": "+ A (Format)",
    "separate_b": "+ B (Proximity)",
    "combined_ab": "+ A+B",
    "separate_c": "+ C (Non-Deg.)",
    "separate_d": "+ D (Entity)",
    "separate_e": "+ E (Number)",
    "combined_cd": "+ C+D",
    "combined_cde": "+ C+D+E",
    "combined_all": "Comb.\\ All",
}
RUN_COLORS = {
    "baseline": "#001219",      # ink-black
    "separate_a": "#005f73",    # dark-teal
    "separate_b": "#0a9396",    # dark-cyan
    "combined_ab": "#94d2bd",   # pearl-aqua
    "separate_c": "#e9d8a6",    # vanilla-custard
    "separate_d": "#ee9b00",    # golden-orange
    "separate_e": "#ca6702",    # burnt-caramel
    "combined_cd": "#bb3e03",   # rusty-spice
    "combined_cde": "#ae2012",  # oxidized-iron
    "combined_all": "#9b2226",  # brown-red
}
# Matplotlib labels: plain space (no LaTeX \\ escape)
MPL_LABELS = {k: v.replace("\\ ", " ") for k, v in RUN_LABELS.items()}

INTERACTION_GROUPS = {
    "combined_ab": {"components": ["separate_a", "separate_b"], "label": "+ A+B"},
    "combined_cd": {"components": ["separate_c", "separate_d"], "label": "+ C+D"},
    "combined_cde": {"components": ["separate_c", "separate_d", "separate_e"], "label": "+ C+D+E"},
    "combined_all": {"components": ["separate_a", "separate_b", "separate_c", "separate_d", "separate_e"], "label": "Comb. All"},
}

ERROR_CATEGORIES = [
    "no_answer", "format_only", "no_reasoning",
    "arithmetic_error", "large_error", "gibberish",
]
ERROR_LABELS = {
    "no_answer": "No answer",
    "format_only": "Format only",
    "no_reasoning": "No reasoning",
    "arithmetic_error": "Arithmetic error",
    "large_error": "Large error",
    "gibberish": "Gibberish",
}
ERROR_COLORS = {
    "no_answer": "#f9c74f",       # tuscan-sun
    "format_only": "#90be6d",     # willow-green
    "no_reasoning": "#43aa8b",    # seagrass
    "arithmetic_error": "#4d908e",# dark-cyan
    "large_error": "#577590",     # blue-slate
    "gibberish": "#277da1",       # cerulean
}

# Contrasting color pairs for side-by-side comparisons
CONTRAST_1A = ["#f72585", "#b5179e", "#7209b7", "#560bad"]  # neon-pink → ultrasonic-blue
CONTRAST_1B = ["#3f37c9", "#4361ee", "#4895ef", "#4cc9f0"]  # bright-indigo → sky-aqua
CONTRAST_2A = ["#0466c8", "#0353a4", "#023e7d", "#002855"]  # smart-blue → prussian-blue
CONTRAST_2B = ["#33415c", "#5c677d", "#7d8597", "#979dac"]  # twilight-indigo → lavender-grey

RC_PARAMS = {
    "font.size": 9,
    "font.family": "serif",
    "lines.linewidth": 1.0,
    "axes.linewidth": 0.5,
    "mathtext.fontset": "stix",
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "figure.figsize": (3.5, 2.5),
}


def _apply_rc():
    plt.rcParams.update(RC_PARAMS)


def _style_ax(ax):
    """Remove top/right spines for cleaner academic look."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _available_runs(data: dict) -> list[str]:
    """Return runs from RUN_ORDER that exist in the data."""
    return [r for r in RUN_ORDER if r in data["runs"]]


# ---------------------------------------------------------------------------
# T1: Summary Results Table
# ---------------------------------------------------------------------------

def _produce_t1(data: dict, output_dir: str, runs: list[str], filename: str, caption: str, label: str):
    """Summary table for a given set of runs."""
    baseline_pass1 = data["runs"].get("baseline", {}).get("metrics", {}).get("pass1", 0)

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(r"\begin{tabular}{lrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"Run & Pass@1 (\%) & Pass@8 (\%) & Gap (\%) & Extr.\ Fail (\%) & $\Delta$ Pass@1 \\")
    lines.append(r"\midrule")

    # Find best values for bolding
    all_pass1 = [data["runs"][r]["metrics"]["pass1"] for r in runs]
    all_pass8 = [data["runs"][r]["metrics"]["pass8"] for r in runs]
    all_extr = [data["runs"][r]["metrics"]["extraction_failure_rate"] for r in runs]
    best_pass1 = max(all_pass1)
    best_pass8 = max(all_pass8)
    best_extr = min(all_extr)
    # Gap: smallest is best (most consistent)
    all_gaps = [data["runs"][r]["metrics"]["pass8_pass1_gap"] for r in runs]
    best_gap = min(all_gaps)

    for i, name in enumerate(runs):
        m = data["runs"][name]["metrics"]
        label = RUN_LABELS.get(name, name)
        p1 = m["pass1"] * 100
        p8 = m["pass8"] * 100
        gap = m["pass8_pass1_gap"] * 100
        extr = m["extraction_failure_rate"] * 100
        delta = (m["pass1"] - baseline_pass1) * 100

        def _bold(val, fmt, is_best):
            s = f"{val:{fmt}}"
            return rf"\textbf{{{s}}}" if is_best else s

        p1_s = _bold(p1, ".1f", m["pass1"] == best_pass1)
        p8_s = _bold(p8, ".1f", m["pass8"] == best_pass8)
        gap_s = _bold(gap, ".1f", m["pass8_pass1_gap"] == best_gap)
        extr_s = _bold(extr, ".1f", m["extraction_failure_rate"] == best_extr)
        delta_s = f"{delta:+.1f}" if name != "baseline" else "---"

        lines.append(f"{label} & {p1_s} & {p8_s} & {gap_s} & {extr_s} & {delta_s} \\\\")
        if i == 0 or name == "combined_ab" or name == "combined_cde":
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] {filename} saved to {path}")


def produce_t1(data: dict, output_dir: str):
    """Summary table: all runs (post-P3)."""
    runs = _available_runs(data)
    _produce_t1(data, output_dir, runs, "t1_summary.tex",
                r"Summary of evaluation results across all ten runs. Best per column in \textbf{bold}.",
                "tab:p4-summary-full")


def produce_t1_pre(data: dict, output_dir: str):
    """Summary table: pre-P3 runs only."""
    runs = [r for r in PRE_P3_RUNS if r in data["runs"]]
    _produce_t1(data, output_dir, runs, "t1_summary_pre.tex",
                r"Summary of evaluation results (pre-P3 runs). Pass@1 and Pass@8 over 1319 GSM8K test problems (8 samples each). Gap = Pass@8 $-$ Pass@1. Extr.\ Fail = extraction failure rate. $\Delta$Pass@1 = pp change vs.\ Baseline. Best per column in \textbf{bold}.",
                "tab:p4-summary")


# ---------------------------------------------------------------------------
# T2: Gained/Lost Delta Table
# ---------------------------------------------------------------------------

def _produce_t2(data: dict, output_dir: str, run_list: list[str], filename: str, caption: str, label: str):
    """Per-problem correctness changes vs Baseline. LaTeX tabular."""
    comps = data["comparisons"].get("comparisons", {})
    runs = [r for r in run_list if r != "baseline" and r in comps]

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(r"\begin{tabular}{lrrr}")
    lines.append(r"\toprule")
    lines.append(r"Run & Gained & Lost & Net \\")
    lines.append(r"\midrule")

    for name in runs:
        c = comps[name]
        label_text = RUN_LABELS.get(name, name)
        gained = c["gained_count"]
        lost = c["lost_count"]
        net = c["net_delta"]
        net_s = rf"\textbf{{{net}}}" if abs(net) >= 26 else str(net)
        lines.append(f"{label_text} & {gained} & {lost} & {net_s} \\\\")
        if name == "combined_ab" or name == "combined_cde":
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] {filename} saved to {path}")


def produce_t2(data: dict, output_dir: str):
    """Gained/lost table: all runs (post-P3)."""
    _produce_t2(data, output_dir, RUN_ORDER, "t2_gained_lost.tex",
                r"Per-problem correctness changes vs.\ Baseline across all ten runs.",
                "tab:p4-gained-lost-full")


def produce_t2_pre(data: dict, output_dir: str):
    """Gained/lost table: pre-P3 runs only."""
    _produce_t2(data, output_dir, PRE_P3_RUNS, "t2_gained_lost_pre.tex",
                r"Per-problem correctness changes vs.\ Baseline (pre-P3 runs). Net = Gained $-$ Lost.",
                "tab:p4-gained-lost")


# ---------------------------------------------------------------------------
# T3: Synergy Analysis Table
# ---------------------------------------------------------------------------

def produce_t3(data: dict, output_dir: str):
    """Synergy: Combined vs sum of individual improvements. LaTeX tabular."""
    syn = data["comparisons"].get("synergy", {})
    comps = data["comparisons"].get("comparisons", {})
    if not syn:
        print("[produce] T3 skipped — no synergy data")
        return

    sep_runs = [r for r in RUN_ORDER if r.startswith("separate_") and r in comps]

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Synergy analysis: Combined vs sum of individual improvements.}")

    # Build header
    sep_headers = " & ".join(rf"$\Delta$ {RUN_LABELS.get(r, r)}" for r in sep_runs)
    lines.append(r"\begin{tabular}{l" + "r" * len(sep_runs) + "rrr}")
    lines.append(r"\toprule")
    lines.append(f"Metric & {sep_headers} & Sum & Combined $\\Delta$ & Pattern \\\\")
    lines.append(r"\midrule")

    # Pass@1 row
    sep_vals = [f"{comps[r]['delta_pass1_pp']:+.1f}" for r in sep_runs]
    sum_val = syn["sum_of_separate_deltas"] * 100
    comb_val = syn["combined_delta_pass1"] * 100
    pattern = syn["pattern"].capitalize()
    lines.append(f"Pass@1 (pp) & {' & '.join(sep_vals)} & {sum_val:+.1f} & {comb_val:+.1f} & {pattern} \\\\")

    # Problems gained row
    sep_gained = [str(comps[r]["gained_count"]) for r in sep_runs]
    sum_gained = sum(comps[r]["gained_count"] for r in sep_runs)
    comb_gained = comps.get("combined", {}).get("gained_count", 0)
    lines.append(f"Problems gained & {' & '.join(sep_gained)} & {sum_gained} & {comb_gained} & --- \\\\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "t3_synergy.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] T3 saved to {path}")


# ---------------------------------------------------------------------------
# T4: Error Distribution Table (pre-P3 and post-P3)
# ---------------------------------------------------------------------------

PRE_P3_RUNS = ["baseline", "separate_a", "separate_b", "combined_ab"]
POST_P3_RUNS = RUN_ORDER  # all 10

def _produce_error_table(data: dict, output_dir: str, runs: list[str], filename: str, caption: str, label: str):
    """Error distribution table for a given set of runs."""
    available = [r for r in runs if r in data["runs"]]
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\small")
    lines.append(r"\begin{tabular}{lrrrrrr}")
    lines.append(r"\toprule")
    lines.append(r"\textbf{Run} & \textbf{No Ans.} & \textbf{Fmt Only} & \textbf{No Reas.} & \textbf{Arith.} & \textbf{Wrong Set.} & \textbf{Gibb.} \\")
    lines.append(r"\midrule")

    for i, name in enumerate(available):
        mc = data["runs"][name]["mistake_counts"]
        mp = data["runs"][name]["mistake_pcts"]
        label_text = RUN_LABELS.get(name, name)

        cells = []
        for cat in ERROR_CATEGORIES:
            count = mc.get(cat, 0)
            pct = mp.get(cat, 0.0)
            if count == 0 and pct == 0:
                cells.append("0")
            else:
                cells.append(f"{count} ({pct:.1f}\\%)")
        lines.append(f"{label_text} & {' & '.join(cells)} \\\\")
        if i == 0:
            lines.append(r"\midrule")
        # Add midrule between groups for post-P3
        elif name == "combined_ab" and len(available) > 4:
            lines.append(r"\midrule")
        elif name == "combined_cde" and len(available) > 4:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(f"\\caption{{{caption}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] {filename} saved to {path}")


def produce_t4_pre(data: dict, output_dir: str):
    """Error table for pre-P3 runs (4 runs)."""
    _produce_error_table(
        data, output_dir, PRE_P3_RUNS,
        "t4_errors_pre.tex",
        r"Mistake type distribution for problems where all 8 samples failed (pre-P3 runs). Percentages are within each run's failed set.",
        "tab:p4-errors",
    )


def produce_t4_post(data: dict, output_dir: str):
    """Error table for all 10 runs."""
    _produce_error_table(
        data, output_dir, POST_P3_RUNS,
        "t4_errors_post.tex",
        r"Mistake type distribution across all ten runs. Percentages are within each run's failed set (problems where all 8 samples failed).",
        "tab:p4-errors-full",
    )


# ---------------------------------------------------------------------------
# T5: Ablation Design Table
# ---------------------------------------------------------------------------

REWARD_LETTERS = ["A", "B", "C", "D", "E"]
REWARD_DESCRIPTIONS = {
    "A": "Format", "B": "Proximity", "C": "Coherence", "D": "Entity", "E": "Number",
}
ABLATION_MATRIX = {
    "baseline":     {"A": False, "B": False, "C": False, "D": False, "E": False},
    "separate_a":   {"A": True,  "B": False, "C": False, "D": False, "E": False},
    "separate_b":   {"A": False, "B": True,  "C": False, "D": False, "E": False},
    "combined_ab":  {"A": True,  "B": True,  "C": False, "D": False, "E": False},
    "separate_c":   {"A": False, "B": False, "C": True,  "D": False, "E": False},
    "separate_d":   {"A": False, "B": False, "C": False, "D": True,  "E": False},
    "separate_e":   {"A": False, "B": False, "C": False, "D": False, "E": True},
    "combined_cd":  {"A": False, "B": False, "C": True,  "D": True,  "E": False},
    "combined_cde": {"A": False, "B": False, "C": True,  "D": True,  "E": True},
    "combined_all": {"A": True,  "B": True,  "C": True,  "D": True,  "E": True},
}

def produce_t5(output_dir: str):
    """Ablation design table showing which rewards are active per run."""
    lines = []
    lines.append(r"\begin{table}[H]")
    lines.append(r"\centering")
    lines.append(r"\small")
    headers = " & ".join(rf"\textbf{{{l} ({REWARD_DESCRIPTIONS[l]})}}" for l in REWARD_LETTERS)
    lines.append(r"\begin{tabular}{l" + "c" * len(REWARD_LETTERS) + "}")
    lines.append(r"\toprule")
    lines.append(rf"\textbf{{Run}} & {headers} \\")
    lines.append(r"\midrule")

    for i, run in enumerate(RUN_ORDER):
        label = RUN_LABELS.get(run, run)
        cells = []
        for letter in REWARD_LETTERS:
            cells.append(r"\checkmark" if ABLATION_MATRIX[run][letter] else "--")
        lines.append(f"{label} & {' & '.join(cells)} \\\\")
        if i == 0:
            lines.append(r"\midrule")
        elif run == "combined_ab":
            lines.append(r"\midrule")
        elif run == "combined_cde":
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\caption{Reward composition per run. All runs include the binary correctness reward (omitted from columns for clarity). ``+~X'' = correctness + reward X; letter combinations = correctness + all listed rewards.}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "t5_ablation.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] T5 saved to {path}")


# ---------------------------------------------------------------------------
# Macros: p4_macros.tex
# ---------------------------------------------------------------------------

def produce_macros(data: dict, output_dir: str):
    """Generate LaTeX newcommand macros for all key numbers."""
    comps = data["comparisons"].get("comparisons", {})
    macros = []
    macros.append("% Auto-generated by produce.py — do not edit by hand")
    macros.append("")

    # Total problems
    n_problems = data["runs"]["baseline"]["n_problems"]
    macros.append(f"\\newcommand{{\\pFourNProblems}}{{{n_problems}}}")

    # Per-run metrics
    for run in RUN_ORDER:
        if run not in data["runs"]:
            continue
        m = data["runs"][run]["metrics"]
        mc = data["runs"][run]["mistake_counts"]
        mp = data["runs"][run]["mistake_pcts"]
        te = data["runs"][run]["total_errors"]

        # Create a camelCase tag from run name
        tag = run.replace("_", " ").title().replace(" ", "")
        # e.g., baseline -> Baseline, separate_a -> SeparateA, combined_all -> CombinedAll

        # Core metrics
        macros.append(f"\\newcommand{{\\pFour{tag}PassOne}}{{{m['pass1']*100:.1f}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}PassEight}}{{{m['pass8']*100:.1f}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}Gap}}{{{m['pass8_pass1_gap']*100:.1f}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}ExtrFail}}{{{m['extraction_failure_rate']*100:.1f}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}PassOneCount}}{{{m['pass1_count']}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}PassEightCount}}{{{m['pass8_count']}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}TotalErrors}}{{{te}}}")

        # Error percentages
        for cat in ERROR_CATEGORIES:
            cat_tag = cat.replace("_", " ").title().replace(" ", "")
            macros.append(f"\\newcommand{{\\pFour{tag}{cat_tag}}}{{{mp.get(cat, 0):.1f}}}")

        # Error counts
        for cat in ERROR_CATEGORIES:
            cat_tag = cat.replace("_", " ").title().replace(" ", "")
            macros.append(f"\\newcommand{{\\pFour{tag}{cat_tag}Count}}{{{mc.get(cat, 0)}}}")

        macros.append("")

    # Delta metrics from comparisons
    for run in RUN_ORDER:
        if run == "baseline" or run not in comps:
            continue
        c = comps[run]
        tag = run.replace("_", " ").title().replace(" ", "")
        macros.append(f"\\newcommand{{\\pFour{tag}DeltaPassOne}}{{{c['delta_pass1_pp']:+.1f}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}Gained}}{{{c['gained_count']}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}Lost}}{{{c['lost_count']}}}")
        macros.append(f"\\newcommand{{\\pFour{tag}Net}}{{{c['net_delta']}}}")

    macros.append("")

    # Derived values used in prose
    # Format failure rate for baseline
    bl_fmt = data["runs"]["baseline"]["mistake_pcts"]["no_answer"] + data["runs"]["baseline"]["mistake_pcts"]["format_only"]
    macros.append(f"\\newcommand{{\\pFourBaselineFmtFailPct}}{{{bl_fmt:.1f}}}")

    # Format failure rate for + A
    a_fmt = data["runs"]["separate_a"]["mistake_pcts"]["no_answer"] + data["runs"]["separate_a"]["mistake_pcts"]["format_only"]
    macros.append(f"\\newcommand{{\\pFourSeparateAFmtFailPct}}{{{a_fmt:.1f}}}")

    # Format failure rate for Comb All
    ca_fmt = data["runs"]["combined_all"]["mistake_pcts"]["no_answer"] + data["runs"]["combined_all"]["mistake_pcts"]["format_only"]
    macros.append(f"\\newcommand{{\\pFourCombinedAllFmtFailPct}}{{{ca_fmt:.1f}}}")

    # Reasoning failure rate for Comb All (arith + large_error)
    ca_reason = data["runs"]["combined_all"]["mistake_pcts"]["arithmetic_error"] + data["runs"]["combined_all"]["mistake_pcts"]["large_error"]
    macros.append(f"\\newcommand{{\\pFourCombinedAllReasonPct}}{{{ca_reason:.1f}}}")

    # Loss stability range
    all_lost = [comps[r]["lost_count"] for r in RUN_ORDER if r != "baseline" and r in comps]
    macros.append(f"\\newcommand{{\\pFourLossMin}}{{{min(all_lost)}}}")
    macros.append(f"\\newcommand{{\\pFourLossMax}}{{{max(all_lost)}}}")

    path = os.path.join(output_dir, "p4_macros.tex")
    with open(path, "w") as f:
        f.write("\n".join(macros))
    print(f"[produce] macros saved to {path}")


# ---------------------------------------------------------------------------
# Fig 2: Individual Impact — (a) Pass@1 ranking, (b) Gained vs lost
# ---------------------------------------------------------------------------

def produce_fig2(data: dict, output_dir: str):
    """Fig 2: Individual Impact — (a) Pass@1 ranking, (b) Gained vs lost."""
    _apply_rc()
    comps = data["comparisons"].get("comparisons", {})
    runs = _available_runs(data)

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(10, 4))

    # Panel (a): Pass@1 ranking horizontal bars
    runs_sorted = sorted(runs, key=lambda r: data["runs"][r]["metrics"]["pass1"])
    labels = [MPL_LABELS.get(r, r) for r in runs_sorted]
    values = [data["runs"][r]["metrics"]["pass1"] * 100 for r in runs_sorted]
    colors = [RUN_COLORS.get(r, "#666666") for r in runs_sorted]

    bars = ax_a.barh(range(len(runs_sorted)), values, color=colors,
                     edgecolor="white", linewidth=0.3, height=0.6)
    for bar, val in zip(bars, values):
        ax_a.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                  f"{val:.1f}%", va="center", fontsize=7)

    baseline_val = data["runs"]["baseline"]["metrics"]["pass1"] * 100
    ax_a.axvline(baseline_val, color=RUN_COLORS["baseline"], linewidth=0.8, linestyle="--", alpha=0.7)
    ax_a.set_yticks(range(len(runs_sorted)))
    ax_a.set_yticklabels(labels, fontsize=7)
    ax_a.set_xlabel("Pass@1 (%)")
    ax_a.set_title("(a) Pass@1 ranking")
    ax_a.set_xlim(0, max(values) + 3)
    _style_ax(ax_a)

    # Panel (b): Gained vs lost
    run_list = [r for r in RUN_ORDER if r != "baseline" and r in comps]
    x = range(len(run_list))
    gained = [comps[r]["gained_count"] for r in run_list]
    lost = [-comps[r]["lost_count"] for r in run_list]

    ax_b.bar(x, gained, color=CONTRAST_1B[2], label="Gained", width=0.6,
             edgecolor="white", linewidth=0.3)
    ax_b.bar(x, lost, color=CONTRAST_1A[0], label="Lost", width=0.6,
             edgecolor="white", linewidth=0.3)

    for i, (g, l) in enumerate(zip(gained, lost)):
        ax_b.text(i, g + 2, str(g), ha="center", va="bottom", fontsize=7, color=CONTRAST_1B[2])
        ax_b.text(i, l - 2, str(-l), ha="center", va="top", fontsize=7, color=CONTRAST_1A[0])

    all_lost = [comps[r]["lost_count"] for r in run_list]
    loss_min, loss_max = min(all_lost), max(all_lost)
    ax_b.axhline(-loss_min, color=CONTRAST_1A[0], linewidth=0.5, linestyle="--", alpha=0.4)
    ax_b.axhline(-loss_max, color=CONTRAST_1A[0], linewidth=0.5, linestyle="--", alpha=0.4)
    ax_b.fill_between([-0.5, len(run_list) - 0.5], -loss_max, -loss_min,
                      color=CONTRAST_1A[0], alpha=0.05)

    ax_b.axhline(0, color="black", linewidth=0.5)
    ax_b.set_xticks(list(x))
    ax_b.set_xticklabels([MPL_LABELS.get(r, r) for r in run_list],
                         rotation=30, ha="right", fontsize=7)
    ax_b.set_ylabel("Problems")
    ax_b.set_title("(b) Gained vs lost relative to Baseline")
    ax_b.legend(fontsize=7, loc="upper left")
    _style_ax(ax_b)

    fig.tight_layout()
    path = os.path.join(output_dir, "fig2_individual_impact.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] Fig 2 saved to {path}")


# ---------------------------------------------------------------------------
# Fig 3: Interactions — (a) Expected vs actual, (b) Combined vs best component
# ---------------------------------------------------------------------------

def produce_fig3(data: dict, output_dir: str):
    """Fig 3: Interactions — (a) Expected vs actual ΔPass@1, (b) Δ vs best component."""
    _apply_rc()
    baseline_p1 = data["runs"]["baseline"]["metrics"]["pass1"]
    baseline_p8 = data["runs"]["baseline"]["metrics"]["pass8"]

    groups = [g for g in INTERACTION_GROUPS if g in data["runs"]]
    group_labels = [INTERACTION_GROUPS[g]["label"] for g in groups]

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(10, 4))

    # Panel (a): Expected vs Actual ΔPass@1
    expected = []
    actual = []
    for g in groups:
        components = INTERACTION_GROUPS[g]["components"]
        exp_sum = sum((data["runs"][c]["metrics"]["pass1"] - baseline_p1) * 100
                      for c in components if c in data["runs"])
        act_delta = (data["runs"][g]["metrics"]["pass1"] - baseline_p1) * 100
        expected.append(exp_sum)
        actual.append(act_delta)

    x = list(range(len(groups)))
    w = 0.35
    ax_a.bar([i - w / 2 for i in x], expected, width=w, color=CONTRAST_2B[2],
             edgecolor="white", linewidth=0.3, label="Expected (sum)", hatch="//")
    ax_a.bar([i + w / 2 for i in x], actual, width=w, color=CONTRAST_2A[0],
             edgecolor="white", linewidth=0.3, label="Actual")

    for i, (e, a) in enumerate(zip(expected, actual)):
        ax_a.text(i - w / 2, e + 0.3, f"{e:+.1f}", ha="center", va="bottom",
                  fontsize=7, color=CONTRAST_2B[2])
        ax_a.text(i + w / 2, a + 0.3, f"{a:+.1f}", ha="center", va="bottom",
                  fontsize=7, color=CONTRAST_2A[0])

    ax_a.set_xticks(x)
    ax_a.set_xticklabels(group_labels, fontsize=8)
    ax_a.set_ylabel("$\\Delta$Pass@1 (pp)")
    ax_a.set_title("(a) Expected vs actual improvement")
    ax_a.legend(fontsize=7, loc="upper left")
    ax_a.axhline(0, color="black", linewidth=0.5)
    _style_ax(ax_a)

    # Panel (b): Δ vs best component on Pass@1 and Pass@8
    delta_p1 = []
    delta_p8 = []
    for g in groups:
        components = [c for c in INTERACTION_GROUPS[g]["components"] if c in data["runs"]]
        best_comp_p1 = max(data["runs"][c]["metrics"]["pass1"] for c in components) * 100
        best_comp_p8 = max(data["runs"][c]["metrics"]["pass8"] for c in components) * 100
        comb_p1 = data["runs"][g]["metrics"]["pass1"] * 100
        comb_p8 = data["runs"][g]["metrics"]["pass8"] * 100
        delta_p1.append(comb_p1 - best_comp_p1)
        delta_p8.append(comb_p8 - best_comp_p8)

    ax_b.bar([i - w / 2 for i in x], delta_p1, width=w, color=CONTRAST_1A[2],
             edgecolor="white", linewidth=0.3, label="Pass@1")
    ax_b.bar([i + w / 2 for i in x], delta_p8, width=w, color=CONTRAST_1B[2],
             edgecolor="white", linewidth=0.3, label="Pass@8")

    for i, (d1, d8) in enumerate(zip(delta_p1, delta_p8)):
        va1 = "bottom" if d1 >= 0 else "top"
        va8 = "bottom" if d8 >= 0 else "top"
        off1 = 0.2 if d1 >= 0 else -0.2
        off8 = 0.2 if d8 >= 0 else -0.2
        ax_b.text(i - w / 2, d1 + off1, f"{d1:+.1f}", ha="center", va=va1,
                  fontsize=7, color=CONTRAST_1A[2])
        ax_b.text(i + w / 2, d8 + off8, f"{d8:+.1f}", ha="center", va=va8,
                  fontsize=7, color=CONTRAST_1B[2])

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(group_labels, fontsize=8)
    ax_b.set_ylabel("$\\Delta$ vs best component (pp)")
    ax_b.set_title("(b) Combined vs best individual")
    ax_b.legend(fontsize=7, loc="best")
    ax_b.axhline(0, color="black", linewidth=0.5)
    _style_ax(ax_b)

    fig.tight_layout()
    path = os.path.join(output_dir, "fig3_interactions.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] Fig 3 saved to {path}")


# ---------------------------------------------------------------------------
# Fig 4: Error Distribution — stacked bar (percentages only)
# ---------------------------------------------------------------------------

def produce_fig4(data: dict, output_dir: str):
    """Fig 4: Error Distribution — stacked bar (percentages only)."""
    _apply_rc()
    runs = _available_runs(data)

    fig, ax = plt.subplots(figsize=(7, 3.5))
    x = range(len(runs))
    bottoms = [0.0] * len(runs)

    for cat in ERROR_CATEGORIES:
        vals = [data["runs"][r]["mistake_pcts"].get(cat, 0) for r in runs]
        ax.bar(x, vals, bottom=bottoms, color=ERROR_COLORS[cat],
               label=ERROR_LABELS[cat], width=0.6, edgecolor="white", linewidth=0.3)

        for i, (v, b) in enumerate(zip(vals, bottoms)):
            if v >= 5:
                ax.text(i, b + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=6)

        bottoms = [b + v for b, v in zip(bottoms, vals)]

    ax.set_xticks(list(x))
    ax.set_xticklabels([MPL_LABELS.get(r, r) for r in runs],
                       rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("Percentage (%)")
    ax.legend(fontsize=7, loc="upper right", bbox_to_anchor=(1.25, 1.0))
    _style_ax(ax)

    fig.tight_layout()
    path = os.path.join(output_dir, "fig4_error_distribution.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] Fig 4 saved to {path}")


# ---------------------------------------------------------------------------
# Fig 5: Training Dynamics — 4×1 vertical: reward, pass@1, components, seq length
# ---------------------------------------------------------------------------

def _smooth(values, window=15):
    """Simple moving average for noisy training curves."""
    import numpy as np
    # Replace None with NaN, then interpolate
    clean = [v if v is not None else float('nan') for v in values]
    arr = np.array(clean, dtype=float)
    # Forward-fill NaNs
    mask = np.isnan(arr)
    if mask.all():
        return values
    if mask.any():
        arr[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), arr[~mask])
    if len(arr) < window:
        return list(arr)
    kernel = np.ones(window) / window
    smoothed = np.convolve(arr, kernel, mode="valid")
    pad = list(arr[:len(arr) - len(smoothed)])
    return pad + list(smoothed)


def produce_fig5(wandb_data: dict, output_dir: str):
    """Fig 5: Training Dynamics — 4×1 vertical: reward, pass@1, components, seq length."""
    _apply_rc()

    # Remap logged component names to paper names
    COMPONENT_DISPLAY = {
        "coherence": "non-degeneracy",
        "correctness": "correctness",
        "entity_grounding": "entity grounding",
        "format_compliance": "format compliance",
        "number_grounding": "number grounding",
        "numeric_proximity": "numeric proximity",
    }

    panel_w, panel_h = 7, 7 / 3  # 1:3 height:width ratio per panel
    fig, (ax_a, ax_b, ax_c, ax_d) = plt.subplots(4, 1, figsize=(panel_w, panel_h * 4), sharex=True)

    # Panel (a): Mean reward curves (smoothed)
    for run_name in RUN_ORDER:
        if run_name not in wandb_data:
            continue
        history = wandb_data[run_name].get("history", [])
        steps = [r["_step"] for r in history if "reward" in r]
        rewards = [r["reward"] for r in history if "reward" in r]
        if steps:
            ax_a.plot(steps, _smooth(rewards), color=RUN_COLORS.get(run_name, "gray"),
                      label=MPL_LABELS.get(run_name, run_name),
                      linewidth=1.0, alpha=0.8)

    ax_a.set_ylabel("Mean reward")
    ax_a.set_title("(a) Reward curves")
    ax_a.legend(fontsize=5, bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0)
    _style_ax(ax_a)

    # Panel (b): Pass@1 over training (smoothed)
    for run_name in RUN_ORDER:
        if run_name not in wandb_data:
            continue
        history = wandb_data[run_name].get("history", [])
        steps = [r["_step"] for r in history if "pass@1" in r]
        pass1 = [r["pass@1"] for r in history if "pass@1" in r]
        if steps:
            ax_b.plot(steps, _smooth(pass1), color=RUN_COLORS.get(run_name, "gray"),
                      label=MPL_LABELS.get(run_name, run_name),
                      linewidth=1.0, alpha=0.8)

    ax_b.set_ylabel("Pass@1")
    ax_b.set_title("(b) Pass@1")
    ax_b.legend(fontsize=5, bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0)
    _style_ax(ax_b)

    # Panel (c): Per-component rewards (Comb. All, smoothed)
    combined_key = "combined_all" if "combined_all" in wandb_data else "combined_ab"
    if combined_key in wandb_data:
        history = wandb_data[combined_key].get("history", [])
        component_keys = set()
        for row in history:
            for key in row:
                if key.startswith("reward/") or key.startswith("reward_"):
                    component_keys.add(key)

        component_colors = [CONTRAST_2A[0], CONTRAST_2A[2], CONTRAST_1A[0], CONTRAST_1A[2], CONTRAST_1B[1], CONTRAST_1B[3]]
        for i, key in enumerate(sorted(component_keys)):
            steps = [r["_step"] for r in history if key in r]
            vals = [r[key] for r in history if key in r]
            if steps:
                raw_label = key.replace("reward/", "").replace("reward_", "")
                label = COMPONENT_DISPLAY.get(raw_label, raw_label)
                ax_c.plot(steps, _smooth(vals), color=component_colors[i % len(component_colors)],
                          label=label, linewidth=1.0, alpha=0.8)

    ax_c.set_ylabel("Mean reward")
    ax_c.set_title("(c) Component rewards (Comb. All)")
    ax_c.legend(fontsize=5, bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0)
    _style_ax(ax_c)

    # Panel (d): Sequence length (smoothed)
    for run_name in RUN_ORDER:
        if run_name not in wandb_data:
            continue
        history = wandb_data[run_name].get("history", [])
        key = None
        for candidate in ("sequence_length", "mean_seq_length", "seq_length"):
            if any(candidate in r for r in history):
                key = candidate
                break
        if not key:
            continue
        steps = [r["_step"] for r in history if key in r]
        lengths = [r[key] for r in history if key in r]
        if steps:
            ax_d.plot(steps, _smooth(lengths), color=RUN_COLORS.get(run_name, "gray"),
                      label=MPL_LABELS.get(run_name, run_name),
                      linewidth=1.0, alpha=0.8)

    ax_d.axhline(256, color="gray", linewidth=0.5, linestyle="--", label="Max tokens (256)")
    ax_d.set_xlabel("Training step")
    ax_d.set_ylabel("Mean seq. length (tokens)")
    ax_d.set_title("(d) Sequence length")
    ax_d.legend(fontsize=5, bbox_to_anchor=(1.01, 1), loc="upper left", borderaxespad=0)
    _style_ax(ax_d)

    fig.tight_layout()
    path = os.path.join(output_dir, "fig5_training_dynamics.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] Fig 5 saved to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_wandb_data(wandb_dir: str) -> dict:
    """Load all W&B JSONs from directory."""
    data = {}
    if not wandb_dir or not os.path.isdir(wandb_dir):
        return data
    for filename in sorted(os.listdir(wandb_dir)):
        if not filename.endswith(".json"):
            continue
        name = filename.replace(".json", "")
        with open(os.path.join(wandb_dir, filename)) as f:
            data[name] = json.load(f)
    return data


def produce_all(processed_path: str, output_dir: str, wandb_dir: str | None = None):
    """Generate all assets from processed results."""
    with open(processed_path) as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    # Tables (from processed data)
    produce_t1(data, output_dir)
    produce_t1_pre(data, output_dir)
    produce_t2(data, output_dir)
    produce_t2_pre(data, output_dir)
    produce_t3(data, output_dir)
    produce_t4_pre(data, output_dir)
    produce_t4_post(data, output_dir)
    produce_t5(output_dir)

    # Macros
    produce_macros(data, output_dir)

    # Figures from eval data
    produce_fig2(data, output_dir)
    produce_fig3(data, output_dir)
    produce_fig4(data, output_dir)

    # Figures from W&B data
    wandb_data = load_wandb_data(wandb_dir)
    if wandb_data:
        produce_fig5(wandb_data, output_dir)
    else:
        print("[produce] No W&B data — skipping Fig 5")

    print(f"\n[produce] All assets saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate report-ready assets from processed results")
    parser.add_argument("--processed", required=True, help="Path to processed.json from process.py")
    parser.add_argument("--output-dir", required=True, help="Directory for output assets")
    parser.add_argument("--wandb-dir", default=None, help="Directory of per-run W&B JSONs (for F3-F5)")
    args = parser.parse_args()

    produce_all(args.processed, args.output_dir, args.wandb_dir)


if __name__ == "__main__":
    main()
