"""Produce tool: generate report-ready assets from processed results.

Usage:
    python -m a4.p4.scripts.produce --processed a4/p4/results/processed.json --output-dir a4/p4/results/assets
    python -m a4.p4.scripts.produce --processed a4/p4/results/processed.json --wandb-dir a4/p4/results/collected/wandb --output-dir a4/p4/results/assets

Input:
    --processed: structured JSON from process.py (runs, per_problem, comparisons)
    --wandb-dir: directory of per-run W&B JSONs from collect.py (for F3, F4, F5)

Output (per design-assets.md):
    Tables: T1 (summary), T2 (gained/lost), T3 (synergy) — LaTeX .tex files
    Figures: F1 (error stacked bar), F2 (error delta), F3 (reward curves),
             F4 (component rewards), F5 (seq length) — PDF files
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

RUN_ORDER = ["baseline", "separate_a", "separate_b", "combined_ab", "separate_c", "separate_d", "combined"]
RUN_LABELS = {
    "baseline": "Baseline",
    "separate_a": "+ A (Format)",
    "separate_b": "+ B (Proximity)",
    "combined_ab": "A+B",
    "separate_c": "+ C",
    "separate_d": "+ D",
    "combined": "Combined",
}
RUN_COLORS = {
    "baseline": "#666666",
    "separate_a": "#1f77b4",
    "separate_b": "#ff7f0e",
    "combined_ab": "#17becf",
    "separate_c": "#2ca02c",
    "separate_d": "#d62728",
    "combined": "#9467bd",
}
RUN_MARKERS = {
    "baseline": "o",
    "separate_a": "s",
    "separate_b": "^",
    "combined_ab": "P",
    "separate_c": "v",
    "separate_d": "D",
    "combined": "*",
}

ERROR_CATEGORIES = [
    "no_answer", "format_only", "no_reasoning",
    "arithmetic_error", "wrong_setup", "gibberish",
]
ERROR_LABELS = {
    "no_answer": "No answer",
    "format_only": "Format only",
    "no_reasoning": "No reasoning",
    "arithmetic_error": "Arithmetic error",
    "wrong_setup": "Wrong setup",
    "gibberish": "Gibberish",
}
ERROR_COLORS = {
    "no_answer": "#66c2a5",
    "format_only": "#fc8d62",
    "no_reasoning": "#8da0cb",
    "arithmetic_error": "#e78ac3",
    "wrong_setup": "#a6d854",
    "gibberish": "#ffd92f",
}

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


def _available_runs(data: dict) -> list[str]:
    """Return runs from RUN_ORDER that exist in the data."""
    return [r for r in RUN_ORDER if r in data["runs"]]


# ---------------------------------------------------------------------------
# T1: Summary Results Table
# ---------------------------------------------------------------------------

def produce_t1(data: dict, output_dir: str):
    """Summary table: all runs x headline metrics. LaTeX tabular."""
    runs = _available_runs(data)
    baseline_pass1 = data["runs"].get("baseline", {}).get("metrics", {}).get("pass1", 0)

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Summary of evaluation results across all reward configurations. Best per column in \textbf{bold}. Single run per configuration.}")
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
        if i == 0:
            lines.append(r"\midrule")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "t1_summary.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] T1 saved to {path}")


# ---------------------------------------------------------------------------
# T2: Gained/Lost Delta Table
# ---------------------------------------------------------------------------

def produce_t2(data: dict, output_dir: str):
    """Per-problem correctness changes vs Baseline. LaTeX tabular."""
    comps = data["comparisons"].get("comparisons", {})
    runs = [r for r in RUN_ORDER if r != "baseline" and r in comps]

    lines = []
    lines.append(r"\begin{table}[ht]")
    lines.append(r"\centering")
    lines.append(r"\caption{Per-problem correctness changes vs Baseline. Net = Gained $-$ Lost.}")
    lines.append(r"\begin{tabular}{lrrr}")
    lines.append(r"\toprule")
    lines.append(r"Run & Gained & Lost & Net \\")
    lines.append(r"\midrule")

    for name in runs:
        c = comps[name]
        label = RUN_LABELS.get(name, name)
        gained = c["gained_count"]
        lost = c["lost_count"]
        net = c["net_delta"]
        # Bold net if > 26 (>2% of 1319)
        net_s = rf"\textbf{{{net}}}" if abs(net) >= 26 else str(net)
        lines.append(f"{label} & {gained} & {lost} & {net_s} \\\\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")

    path = os.path.join(output_dir, "t2_gained_lost.tex")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"[produce] T2 saved to {path}")


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
# F1: Error Distribution Stacked Bar
# ---------------------------------------------------------------------------

def produce_f1(data: dict, output_dir: str):
    """Stacked bar chart of error categories per run."""
    _apply_rc()
    runs = _available_runs(data)

    fig, axes = plt.subplots(1, 2, figsize=(7, 2.5))

    for ax_idx, mode in enumerate(["counts", "pcts"]):
        ax = axes[ax_idx]
        x = range(len(runs))
        bottoms = [0.0] * len(runs)

        for cat in ERROR_CATEGORIES:
            if mode == "counts":
                vals = [data["runs"][r]["mistake_counts"].get(cat, 0) for r in runs]
            else:
                vals = [data["runs"][r]["mistake_pcts"].get(cat, 0) for r in runs]

            ax.bar(x, vals, bottom=bottoms, color=ERROR_COLORS[cat],
                   label=ERROR_LABELS[cat], width=0.6, edgecolor="white", linewidth=0.3)

            # Add percentage labels inside segments >= 5%
            for i, (v, b) in enumerate(zip(vals, bottoms)):
                pct = data["runs"][runs[i]]["mistake_pcts"].get(cat, 0)
                if pct >= 5:
                    ax.text(i, b + v / 2, f"{pct:.0f}%", ha="center", va="center", fontsize=6)

            bottoms = [b + v for b, v in zip(bottoms, vals)]

        ax.set_xticks(x)
        ax.set_xticklabels([RUN_LABELS.get(r, r) for r in runs], rotation=30, ha="right", fontsize=7)
        ax.set_ylabel("Error count" if mode == "counts" else "Percentage (%)")
        ax.set_title("(a) Absolute" if mode == "counts" else "(b) Composition")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=7, bbox_to_anchor=(0.5, -0.15))
    fig.tight_layout()

    path = os.path.join(output_dir, "fig_error_distribution.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] F1 saved to {path}")


# ---------------------------------------------------------------------------
# F2: Error Delta Bar Chart
# ---------------------------------------------------------------------------

def produce_f2(data: dict, output_dir: str):
    """Grouped bars showing pp change per error category vs Baseline."""
    _apply_rc()
    comps = data["comparisons"].get("comparisons", {})
    runs = [r for r in RUN_ORDER if r != "baseline" and r in comps]

    if not runs:
        print("[produce] F2 skipped — no comparison data")
        return

    fig, ax = plt.subplots(figsize=(7, 2.5))
    n_cats = len(ERROR_CATEGORIES)
    n_runs = len(runs)
    bar_width = 0.8 / n_runs
    x_base = range(n_cats)

    for i, run in enumerate(runs):
        delta = comps[run].get("error_distribution_delta", {})
        vals = [delta.get(cat, 0) for cat in ERROR_CATEGORIES]
        x_pos = [x + (i - n_runs / 2 + 0.5) * bar_width for x in x_base]
        ax.bar(x_pos, vals, width=bar_width, color=RUN_COLORS[run],
               label=RUN_LABELS.get(run, run), edgecolor="white", linewidth=0.3)

    ax.axhline(0, color="black", linewidth=0.5, linestyle="-")
    ax.axhline(5, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.axhline(-5, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
    ax.set_xticks(range(n_cats))
    ax.set_xticklabels([ERROR_LABELS[c] for c in ERROR_CATEGORIES], rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("Change (pp)")
    ax.legend(fontsize=6, loc="best")
    fig.tight_layout()

    path = os.path.join(output_dir, "fig_error_delta.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] F2 saved to {path}")


# ---------------------------------------------------------------------------
# F3: Mean Reward Overlay
# ---------------------------------------------------------------------------

def produce_f3(wandb_data: dict, output_dir: str):
    """Training reward curves for all runs."""
    _apply_rc()
    fig, ax = plt.subplots()

    for run_name in RUN_ORDER:
        if run_name not in wandb_data:
            continue
        history = wandb_data[run_name].get("history", [])
        steps = [r["_step"] for r in history if "mean_reward" in r]
        rewards = [r["mean_reward"] for r in history if "mean_reward" in r]
        if steps:
            ax.plot(steps, rewards, color=RUN_COLORS.get(run_name, "gray"),
                    marker=RUN_MARKERS.get(run_name, "o"), markersize=3,
                    label=RUN_LABELS.get(run_name, run_name))

    ax.set_xlabel("Training step")
    ax.set_ylabel("Mean reward")
    ax.legend(fontsize=6, loc="upper left")
    fig.tight_layout()

    path = os.path.join(output_dir, "fig_reward_curves.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] F3 saved to {path}")


# ---------------------------------------------------------------------------
# F4: Per-Component Reward Plot (Combined run only)
# ---------------------------------------------------------------------------

def produce_f4(wandb_data: dict, output_dir: str):
    """Per-component reward curves for Combined run only."""
    _apply_rc()
    # Use "combined" if available, fall back to "combined_ab"
    combined_key = "combined" if "combined" in wandb_data else "combined_ab"
    if combined_key not in wandb_data:
        print("[produce] F4 skipped — no combined W&B data")
        return

    history = wandb_data[combined_key].get("history", [])
    if not history:
        print("[produce] F4 skipped — empty combined history")
        return

    # Find reward component keys (reward/*)
    component_keys = set()
    for row in history:
        for key in row:
            if key.startswith("reward/") or key.startswith("reward_"):
                component_keys.add(key)

    if not component_keys:
        print("[produce] F4 skipped — no per-component reward keys found")
        return

    fig, ax = plt.subplots()
    component_colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i, key in enumerate(sorted(component_keys)):
        steps = [r["_step"] for r in history if key in r]
        vals = [r[key] for r in history if key in r]
        if steps:
            label = key.replace("reward/", "").replace("reward_", "")
            ax.plot(steps, vals, color=component_colors[i % len(component_colors)],
                    label=label, linewidth=1.0)

    ax.set_xlabel("Training step")
    ax.set_ylabel("Mean reward (per component)")
    ax.legend(fontsize=6, loc="best")
    fig.tight_layout()

    path = os.path.join(output_dir, "fig_component_rewards.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] F4 saved to {path}")


# ---------------------------------------------------------------------------
# F5: Sequence Length Overlay
# ---------------------------------------------------------------------------

def produce_f5(wandb_data: dict, output_dir: str):
    """Sequence length curves for all runs."""
    _apply_rc()
    fig, ax = plt.subplots()

    for run_name in RUN_ORDER:
        if run_name not in wandb_data:
            continue
        history = wandb_data[run_name].get("history", [])
        # Try both key names
        key = None
        for candidate in ("mean_seq_length", "seq_length"):
            if any(candidate in r for r in history):
                key = candidate
                break
        if not key:
            continue

        steps = [r["_step"] for r in history if key in r]
        lengths = [r[key] for r in history if key in r]
        if steps:
            ax.plot(steps, lengths, color=RUN_COLORS.get(run_name, "gray"),
                    marker=RUN_MARKERS.get(run_name, "o"), markersize=3,
                    label=RUN_LABELS.get(run_name, run_name))

    ax.axhline(256, color="gray", linewidth=0.5, linestyle="--", label="Max tokens (256)")
    ax.set_xlabel("Training step")
    ax.set_ylabel("Mean sequence length (tokens)")
    ax.legend(fontsize=6, loc="best")
    fig.tight_layout()

    path = os.path.join(output_dir, "fig_seq_length.pdf")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[produce] F5 saved to {path}")


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
    produce_t2(data, output_dir)
    produce_t3(data, output_dir)

    # Figures from eval data
    produce_f1(data, output_dir)
    produce_f2(data, output_dir)

    # Figures from W&B data
    wandb_data = load_wandb_data(wandb_dir)
    if wandb_data:
        produce_f3(wandb_data, output_dir)
        produce_f4(wandb_data, output_dir)
        produce_f5(wandb_data, output_dir)
    else:
        print("[produce] No W&B data — skipping F3, F4, F5")

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
