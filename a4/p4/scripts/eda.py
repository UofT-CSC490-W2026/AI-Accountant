"""Exploratory Data Analysis: GSM8K problem and answer clustering across RL runs.

Usage:
    python -m a4.p4.scripts.eda --output-dir a4/p4/results/eda

Loads GSM8K test questions, all 4 pre-P3 eval JSONs, and produces:
- Problem-side analysis (difficulty, complexity, topic clustering)
- Answer-side analysis (failure modes, coherence, near-misses, consistency)
- Cross-run transition analysis (what each reward fixes/breaks)
- Figures and summary tables saved to output directory
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RUNS = ["baseline", "separate_a", "separate_b", "combined_ab"]
RUN_LABELS = {
    "baseline": "Baseline",
    "separate_a": "+ A",
    "separate_b": "+ B",
    "combined_ab": "+ A+B",
}
# Project palette — must match produce.py
RUN_COLORS = {
    "baseline": "#001219",
    "separate_a": "#005f73",
    "separate_b": "#0a9396",
    "combined_ab": "#94d2bd",
}
CONTRAST_1A = ["#f72585", "#b5179e", "#7209b7", "#560bad"]
CONTRAST_1B = ["#3f37c9", "#4361ee", "#4895ef", "#4cc9f0"]
CONTRAST_2A = ["#0466c8", "#0353a4", "#023e7d", "#002855"]
CONTRAST_2B = ["#33415c", "#5c677d", "#7d8597", "#979dac"]
EVAL_DIR = "a4/p4/results/collected/eval"
PROCESSED_PATH = "a4/p4/results/processed.json"

# GSM8K gold answer step marker: <<expr=result>>
STEP_RE = re.compile(r"<<[^>]*>>")
# Topic keywords — hand-curated clusters for GSM8K
TOPIC_KEYWORDS = {
    "money/price": ["dollar", "price", "cost", "pay", "sell", "buy", "profit", "earn",
                    "spend", "charge", "discount", "salary", "wage", "rent", "tax", "$"],
    "time/speed": ["hour", "minute", "second", "day", "week", "month", "year", "speed",
                   "fast", "slow", "time", "clock", "travel", "drive", "walk", "run",
                   "mile", "km", "distance"],
    "food/cooking": ["egg", "cookie", "cake", "apple", "orange", "pizza", "bread",
                     "chicken", "meal", "eat", "cook", "recipe", "ingredient", "fruit",
                     "vegetable", "candy", "chocolate"],
    "school/work": ["student", "class", "school", "teacher", "grade", "exam", "test",
                    "homework", "book", "read", "page", "employee", "office", "job"],
    "ratio/fraction": ["ratio", "fraction", "half", "third", "quarter", "twice",
                       "double", "triple", "percent", "%", "proportion"],
    "geometry/area": ["area", "perimeter", "length", "width", "height", "square",
                      "rectangle", "circle", "feet", "foot", "inch", "meter", "yard",
                      "garden", "fence", "wall", "room", "floor"],
    "age": ["age", "old", "young", "born", "birthday", "years older", "years younger"],
    "collection/count": ["collect", "marble", "stamp", "card", "toy", "ball", "flower",
                         "pet", "dog", "cat", "animal", "bird", "fish"],
}


def _apply_rc():
    plt.rcParams.update({
        "figure.figsize": (10, 6),
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "legend.fontsize": 10,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
    })
    sns.set_style("whitegrid")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_gsm8k_questions() -> list[dict]:
    """Load GSM8K test set questions and gold solutions."""
    from datasets import load_dataset
    ds = load_dataset("openai/gsm8k", "main", split="test")
    return [{"question": row["question"], "answer": row["answer"]} for row in ds]


def load_eval_data(eval_dir: str) -> dict[str, list]:
    """Load per-run eval samples."""
    data = {}
    for run in RUNS:
        path = os.path.join(eval_dir, f"{run}.json")
        with open(path) as f:
            d = json.load(f)
        data[run] = d["gsm8k_debug"]["samples"]
    return data


def load_processed(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def extract_problem_features(questions: list[dict]) -> pd.DataFrame:
    """Extract per-problem features from GSM8K questions."""
    rows = []
    for i, q in enumerate(questions):
        question_text = q["question"]
        gold_answer = q["answer"]

        # Number of reasoning steps (count <<...>> in gold)
        n_steps = len(STEP_RE.findall(gold_answer))

        # Question length (words)
        q_words = len(question_text.split())

        # Gold numeric answer
        gold_match = re.search(r"####\s*(.+)", gold_answer)
        gold_num_str = gold_match.group(1).strip().replace(",", "") if gold_match else ""
        try:
            gold_num = float(gold_num_str)
        except (ValueError, TypeError):
            gold_num = np.nan
        answer_magnitude = abs(gold_num) if not np.isnan(gold_num) else np.nan

        # Topic classification (first match)
        q_lower = question_text.lower()
        topic = "other"
        for t, keywords in TOPIC_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                topic = t
                break

        rows.append({
            "idx": i,
            "n_steps": n_steps,
            "q_words": q_words,
            "gold_num_str": gold_num_str,
            "gold_num": gold_num,
            "answer_magnitude": answer_magnitude,
            "topic": topic,
            "question": question_text[:200],  # truncated for display
        })
    return pd.DataFrame(rows)


def extract_response_features(eval_data: dict[str, list]) -> pd.DataFrame:
    """Extract per-problem response features for each run."""
    rows = []
    for run in RUNS:
        samples = eval_data[run]
        for s in samples:
            idx = s["idx"]
            responses = s["responses"]
            ref_num = s["ref_num"]

            n_correct = sum(r["correct"] for r in responses)
            n_parseable = sum(r["parseable"] for r in responses)
            pass1 = responses[0]["correct"]
            pass8 = any(r["correct"] for r in responses)

            # Coherence: avg response length, fraction with ####
            lengths = [len(r["completion"]) for r in responses]
            avg_len = np.mean(lengths)
            has_marker = sum(1 for r in responses if "####" in r["completion"])

            # Near-miss: among parseable-but-wrong, how close is pred to ref?
            near_misses = []
            for r in responses:
                if r["parseable"] and not r["correct"] and ref_num:
                    try:
                        pred = float(r["pred_num"].replace(",", ""))
                        ref = float(ref_num.replace(",", ""))
                        if ref != 0:
                            rel_err = abs(pred - ref) / abs(ref)
                        else:
                            rel_err = abs(pred - ref)
                        near_misses.append(rel_err)
                    except (ValueError, TypeError, AttributeError):
                        pass
            min_rel_err = min(near_misses) if near_misses else np.nan
            avg_rel_err = np.mean(near_misses) if near_misses else np.nan
            has_near_miss = 1 if (near_misses and min(near_misses) < 0.1) else 0

            # Consistency: most common predicted answer among parseable responses
            pred_nums = [r["pred_num"] for r in responses if r["parseable"]]
            if pred_nums:
                most_common_pred, most_common_count = Counter(pred_nums).most_common(1)[0]
                consistency = most_common_count / len(responses)
            else:
                most_common_pred = None
                most_common_count = 0
                consistency = 0.0

            # Gibberish detection: responses with very short or no real words
            gibberish_count = 0
            for r in responses:
                text = r["completion"].strip()
                words = text.split()
                if len(text) < 20 or len(words) < 5:
                    gibberish_count += 1
                elif not any(c.isalpha() for c in text[:50]):
                    gibberish_count += 1

            rows.append({
                "idx": idx,
                "run": run,
                "n_correct": n_correct,
                "n_parseable": n_parseable,
                "pass1": pass1,
                "pass8": pass8,
                "avg_response_len": avg_len,
                "has_marker_count": has_marker,
                "marker_rate": has_marker / len(responses),
                "min_rel_err": min_rel_err,
                "avg_rel_err": avg_rel_err,
                "has_near_miss": has_near_miss,
                "consistency": consistency,
                "most_common_pred": most_common_pred,
                "gibberish_count": gibberish_count,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Analysis & Figures
# ---------------------------------------------------------------------------

def fig_difficulty_tiers(prob_df: pd.DataFrame, resp_df: pd.DataFrame, out: str):
    """How many runs solve each problem? Distribution of difficulty."""
    _apply_rc()

    # pass@1 difficulty: how many runs get it right on first sample
    pass1_pivot = resp_df.pivot(index="idx", columns="run", values="pass1")
    pass1_pivot["n_runs_pass1"] = pass1_pivot.sum(axis=1).astype(int)

    # pass@8 difficulty
    pass8_pivot = resp_df.pivot(index="idx", columns="run", values="pass8")
    pass8_pivot["n_runs_pass8"] = pass8_pivot.sum(axis=1).astype(int)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for ax, col, title in [
        (axes[0], pass1_pivot["n_runs_pass1"], "Pass@1: Runs solving each problem"),
        (axes[1], pass8_pivot["n_runs_pass8"], "Pass@8: Runs solving each problem"),
    ]:
        counts = col.value_counts().sort_index()
        tier_colors = [CONTRAST_2A[0], CONTRAST_2A[1], CONTRAST_2A[2], CONTRAST_2A[3], CONTRAST_2B[0]]
        ax.bar(counts.index, counts.values, color=[tier_colors[i] for i in counts.index],
               edgecolor="white", linewidth=0.3)
        ax.set_xlabel("Number of runs solving the problem (out of 4)")
        ax.set_ylabel("Number of problems")
        ax.set_title(title)
        ax.set_xticks(range(5))
        for i, v in zip(counts.index, counts.values):
            ax.text(i, v + 10, str(v), ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_difficulty_tiers.pdf"))
    plt.close()

    # Return for later use
    prob_df["n_runs_pass1"] = pass1_pivot["n_runs_pass1"].values
    prob_df["n_runs_pass8"] = pass8_pivot["n_runs_pass8"].values
    return prob_df


def fig_complexity_vs_difficulty(prob_df: pd.DataFrame, out: str):
    """Scatter: reasoning steps vs difficulty tier, plus boxplots."""
    _apply_rc()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # 1. Steps vs pass@8 difficulty
    ax = axes[0]
    for tier in range(5):
        mask = prob_df["n_runs_pass8"] == tier
        ax.scatter(
            prob_df.loc[mask, "n_steps"] + np.random.normal(0, 0.1, mask.sum()),
            tier * np.ones(mask.sum()) + np.random.normal(0, 0.05, mask.sum()),
            alpha=0.15, s=10, label=f"{tier} runs"
        )
    ax.set_xlabel("Number of reasoning steps (gold)")
    ax.set_ylabel("Runs solving (pass@8)")
    ax.set_title("Reasoning steps vs difficulty")
    ax.set_yticks(range(5))

    # 2. Boxplot: steps by difficulty tier
    ax = axes[1]
    tiers = []
    for tier in range(5):
        vals = prob_df.loc[prob_df["n_runs_pass8"] == tier, "n_steps"].values
        tiers.append(vals)
    bp = ax.boxplot(tiers, labels=[str(i) for i in range(5)], patch_artist=True)
    box_colors = [CONTRAST_2A[0], CONTRAST_2A[1], CONTRAST_2A[2], CONTRAST_2A[3], CONTRAST_2B[0]]
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
    ax.set_xlabel("Runs solving (pass@8)")
    ax.set_ylabel("Reasoning steps")
    ax.set_title("Step count by difficulty tier")

    # 3. Boxplot: answer magnitude by difficulty tier
    ax = axes[2]
    tiers_mag = []
    for tier in range(5):
        vals = prob_df.loc[prob_df["n_runs_pass8"] == tier, "answer_magnitude"].dropna().values
        # Clip for visualization
        tiers_mag.append(np.clip(vals, 0, 10000))
    bp2 = ax.boxplot(tiers_mag, labels=[str(i) for i in range(5)], patch_artist=True)
    for patch, color in zip(bp2["boxes"], box_colors):
        patch.set_facecolor(color)
    ax.set_xlabel("Runs solving (pass@8)")
    ax.set_ylabel("Answer magnitude (clipped at 10k)")
    ax.set_title("Answer magnitude by difficulty tier")
    ax.set_yscale("symlog", linthresh=10)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_complexity_vs_difficulty.pdf"))
    plt.close()


def fig_topic_breakdown(prob_df: pd.DataFrame, out: str):
    """Topic distribution overall and by difficulty."""
    _apply_rc()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. Topic distribution
    ax = axes[0]
    topic_counts = prob_df["topic"].value_counts()
    n_topics = len(topic_counts)
    topic_colors = [CONTRAST_2A[i % len(CONTRAST_2A)] if i < len(CONTRAST_2A)
                    else CONTRAST_2B[i % len(CONTRAST_2B)] for i in range(n_topics)]
    bars = ax.barh(topic_counts.index, topic_counts.values,
                   color=topic_colors, edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Number of problems")
    ax.set_title("Problem topic distribution")
    for bar, v in zip(bars, topic_counts.values):
        ax.text(v + 5, bar.get_y() + bar.get_height()/2, str(v), va="center", fontsize=9)

    # 2. Pass@8 rate by topic (across all runs)
    ax = axes[1]
    topic_pass8 = prob_df.groupby("topic")["n_runs_pass8"].apply(
        lambda x: (x > 0).mean()
    ).sort_values(ascending=True)
    n_topics2 = len(topic_pass8)
    topic_colors2 = [CONTRAST_2A[i % len(CONTRAST_2A)] if i < len(CONTRAST_2A)
                     else CONTRAST_2B[i % len(CONTRAST_2B)] for i in range(n_topics2)]
    bars2 = ax.barh(topic_pass8.index, topic_pass8.values,
                    color=topic_colors2, edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Fraction solved by at least 1 run (pass@8)")
    ax.set_title("Solve rate by topic")
    ax.set_xlim(0, 1)
    for bar, v in zip(bars2, topic_pass8.values):
        ax.text(v + 0.01, bar.get_y() + bar.get_height()/2, f"{v:.2f}", va="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_topic_breakdown.pdf"))
    plt.close()


def fig_failure_modes_by_run(resp_df: pd.DataFrame, eval_data: dict, processed: dict, out: str):
    """D9 failure mode distribution comparison across runs."""
    _apply_rc()

    categories = ["no_answer", "format_only", "arithmetic_error", "large_error", "gibberish"]
    cat_labels = ["No answer", "Format only", "Arithmetic", "Large error", "Gibberish"]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(categories))
    width = 0.2

    for i, run in enumerate(RUNS):
        pcts = [processed["runs"][run]["mistake_pcts"].get(c, 0) for c in categories]
        ax.bar(x + i * width, pcts, width, label=RUN_LABELS[run], color=RUN_COLORS[run],
               edgecolor="white", linewidth=0.3)

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(cat_labels)
    ax.set_ylabel("% of incorrect responses")
    ax.set_title("Failure mode distribution by run (D9 taxonomy)")
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_failure_modes.pdf"))
    plt.close()


def fig_coherence_analysis(resp_df: pd.DataFrame, out: str):
    """Response coherence: length, marker rate, gibberish across runs."""
    _apply_rc()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # 1. Average response length distribution
    ax = axes[0]
    for run in RUNS:
        vals = resp_df.loc[resp_df["run"] == run, "avg_response_len"]
        ax.hist(vals, bins=50, alpha=0.5, label=RUN_LABELS[run], density=True,
                color=RUN_COLORS[run])
    ax.set_xlabel("Average response length (chars)")
    ax.set_ylabel("Density")
    ax.set_title("Response length distribution")
    ax.legend(fontsize=8)
    ax.set_xlim(0, 2000)

    # 2. Marker rate (#### present)
    ax = axes[1]
    marker_rates = resp_df.groupby("run")["marker_rate"].mean()
    bars = ax.bar([RUN_LABELS[r] for r in RUNS],
                  [marker_rates[r] for r in RUNS],
                  color=[RUN_COLORS[r] for r in RUNS], edgecolor="white", linewidth=0.3)
    ax.set_ylabel("Avg fraction of responses with ####")
    ax.set_title("Format marker (####) presence")
    ax.set_ylim(0, 1)
    for bar, v in zip(bars, [marker_rates[r] for r in RUNS]):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02, f"{v:.2f}", ha="center", fontsize=10)

    # 3. Gibberish rate
    ax = axes[2]
    gib_rates = resp_df.groupby("run")["gibberish_count"].apply(lambda x: (x > 0).mean())
    bars = ax.bar([RUN_LABELS[r] for r in RUNS],
                  [gib_rates[r] for r in RUNS],
                  color=[RUN_COLORS[r] for r in RUNS], edgecolor="white", linewidth=0.3)
    ax.set_ylabel("Fraction of problems with any gibberish response")
    ax.set_title("Gibberish rate")
    ax.set_ylim(0, 1)
    for bar, v in zip(bars, [gib_rates[r] for r in RUNS]):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.02, f"{v:.2f}", ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_coherence.pdf"))
    plt.close()


def fig_near_miss_analysis(resp_df: pd.DataFrame, out: str):
    """Near-miss analysis: how close are wrong answers?"""
    _apply_rc()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 1. Distribution of minimum relative error (among parseable-but-wrong)
    ax = axes[0]
    for run in RUNS:
        vals = resp_df.loc[(resp_df["run"] == run) & resp_df["min_rel_err"].notna(), "min_rel_err"]
        vals_clipped = vals.clip(upper=5)
        ax.hist(vals_clipped, bins=50, alpha=0.5, label=RUN_LABELS[run], density=True,
                color=RUN_COLORS[run])
    ax.set_xlabel("Minimum relative error (clipped at 5)")
    ax.set_ylabel("Density")
    ax.set_title("Closest wrong answer per problem")
    ax.legend(fontsize=8)
    ax.axvline(0.1, color="#f72585", linestyle="--", alpha=0.5, label="10% threshold")

    # 2. Near-miss rate by run
    ax = axes[1]
    nm_rates = resp_df.groupby("run")["has_near_miss"].mean()
    bars = ax.bar([RUN_LABELS[r] for r in RUNS],
                  [nm_rates[r] for r in RUNS],
                  color=[RUN_COLORS[r] for r in RUNS], edgecolor="white", linewidth=0.3)
    ax.set_ylabel("Fraction of problems with a near-miss (<10% rel error)")
    ax.set_title("Near-miss rate")
    ax.set_ylim(0, 0.5)
    for bar, v in zip(bars, [nm_rates[r] for r in RUNS]):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.01, f"{v:.3f}", ha="center", fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_near_miss.pdf"))
    plt.close()


def fig_consistency(resp_df: pd.DataFrame, out: str):
    """Answer consistency: do 8 samples agree?"""
    _apply_rc()

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 1. Consistency distribution
    ax = axes[0]
    for run in RUNS:
        vals = resp_df.loc[resp_df["run"] == run, "consistency"]
        ax.hist(vals, bins=20, alpha=0.5, label=RUN_LABELS[run], density=True)
    ax.set_xlabel("Consistency (fraction of 8 samples agreeing)")
    ax.set_ylabel("Density")
    ax.set_title("Answer consistency across 8 samples")
    ax.legend(fontsize=8)

    # 2. n_correct distribution
    ax = axes[1]
    for run in RUNS:
        vals = resp_df.loc[resp_df["run"] == run, "n_correct"]
        counts = vals.value_counts().sort_index()
        ax.plot(counts.index, counts.values / len(vals), marker="o", label=RUN_LABELS[run])
    ax.set_xlabel("Number of correct responses (out of 8)")
    ax.set_ylabel("Fraction of problems")
    ax.set_title("Correct count distribution")
    ax.legend(fontsize=8)
    ax.set_xticks(range(9))

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_consistency.pdf"))
    plt.close()


def fig_cross_run_transitions(resp_df: pd.DataFrame, out: str):
    """What does each reward fix/break relative to baseline?"""
    _apply_rc()

    baseline_pass8 = resp_df.loc[resp_df["run"] == "baseline"].set_index("idx")["pass8"]

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    comparison_runs = ["separate_a", "separate_b", "combined_ab"]

    for ax, run in zip(axes, comparison_runs):
        run_pass8 = resp_df.loc[resp_df["run"] == run].set_index("idx")["pass8"]
        common = baseline_pass8.index.intersection(run_pass8.index)

        gained = ((~baseline_pass8.loc[common]) & run_pass8.loc[common]).sum()
        lost = (baseline_pass8.loc[common] & (~run_pass8.loc[common])).sum()
        both_correct = (baseline_pass8.loc[common] & run_pass8.loc[common]).sum()
        both_wrong = ((~baseline_pass8.loc[common]) & (~run_pass8.loc[common])).sum()

        labels = ["Both correct", "Gained", "Lost", "Both wrong"]
        values = [both_correct, gained, lost, both_wrong]
        colors_pie = ["#4895ef", "#4cc9f0", "#f72585", "#979dac"]

        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct=lambda p: f"{p:.1f}%\n({int(p*len(common)/100)})",
            colors=colors_pie, startangle=90
        )
        ax.set_title(f"{RUN_LABELS[run]} vs Baseline (pass@8)")

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_transitions.pdf"))
    plt.close()


def fig_topic_x_run(prob_df: pd.DataFrame, resp_df: pd.DataFrame, out: str):
    """Heatmap: pass@8 rate by topic and run."""
    _apply_rc()

    merged = resp_df.merge(prob_df[["idx", "topic"]], on="idx")
    pivot = merged.groupby(["topic", "run"])["pass8"].mean().unstack(fill_value=0)
    pivot = pivot[[r for r in RUNS if r in pivot.columns]]
    pivot.columns = [RUN_LABELS[c] for c in pivot.columns]
    pivot = pivot.sort_values(pivot.columns[0], ascending=False)

    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="YlGnBu", ax=ax,
                linewidths=0.5, vmin=0, vmax=0.6)
    ax.set_title("Pass@8 rate by topic and run")
    ax.set_ylabel("Topic")

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_topic_x_run.pdf"))
    plt.close()


def fig_step_count_pass_rate(prob_df: pd.DataFrame, resp_df: pd.DataFrame, out: str):
    """Pass rate by number of reasoning steps in gold solution."""
    _apply_rc()

    merged = resp_df.merge(prob_df[["idx", "n_steps"]], on="idx")
    # Bin steps: 1, 2, 3, 4, 5, 6+
    merged["step_bin"] = merged["n_steps"].clip(upper=6)
    merged.loc[merged["step_bin"] >= 6, "step_bin"] = 6

    fig, ax = plt.subplots(figsize=(10, 5))
    for run in RUNS:
        sub = merged[merged["run"] == run]
        rates = sub.groupby("step_bin")["pass8"].mean()
        ax.plot(rates.index, rates.values, marker="o", label=RUN_LABELS[run], linewidth=2)

    ax.set_xlabel("Number of reasoning steps in gold solution")
    ax.set_ylabel("Pass@8 rate")
    ax.set_title("Pass rate by problem complexity (reasoning steps)")
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels(["1", "2", "3", "4", "5", "6+"])
    ax.legend()
    ax.set_ylim(0, 0.7)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_step_count_pass_rate.pdf"))
    plt.close()


# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------

def table_summary(prob_df: pd.DataFrame, resp_df: pd.DataFrame, processed: dict, out: str):
    """Write text summary tables."""
    lines = []
    lines.append("=" * 80)
    lines.append("EDA SUMMARY: GSM8K Problem & Answer Clustering")
    lines.append("=" * 80)

    # Overall metrics
    lines.append("\n--- Per-run metrics ---")
    lines.append(f"{'Run':<20} {'Pass@1':>8} {'Pass@8':>8} {'Gap':>8} {'Extr.Fail':>10} {'Errors':>8}")
    for run in RUNS:
        m = processed["runs"][run]["metrics"]
        te = processed["runs"][run]["total_errors"]
        lines.append(
            f"{RUN_LABELS[run]:<20} {m['pass1']*100:>7.1f}% {m['pass8']*100:>7.1f}% "
            f"{m['pass8_pass1_gap']*100:>7.1f}% {m['extraction_failure_rate']*100:>9.1f}% {te:>8d}"
        )

    # Difficulty tiers
    lines.append("\n--- Difficulty tiers (pass@8, how many of 4 runs solve) ---")
    tier_counts = prob_df["n_runs_pass8"].value_counts().sort_index()
    for tier in range(5):
        n = tier_counts.get(tier, 0)
        lines.append(f"  {tier} runs solve: {n:>5d} problems ({n/len(prob_df)*100:.1f}%)")

    # Topic distribution
    lines.append("\n--- Topic distribution ---")
    topic_counts = prob_df["topic"].value_counts()
    for topic, count in topic_counts.items():
        pass8_any = (prob_df.loc[prob_df["topic"] == topic, "n_runs_pass8"] > 0).mean()
        lines.append(f"  {topic:<20s}: {count:>5d} problems, pass@8 solve rate: {pass8_any:.2f}")

    # Complexity stats
    lines.append("\n--- Complexity stats ---")
    lines.append(f"  Reasoning steps: mean={prob_df['n_steps'].mean():.1f}, "
                 f"median={prob_df['n_steps'].median():.0f}, "
                 f"max={prob_df['n_steps'].max()}")
    lines.append(f"  Question words:  mean={prob_df['q_words'].mean():.1f}, "
                 f"median={prob_df['q_words'].median():.0f}")
    lines.append(f"  Answer magnitude: median={prob_df['answer_magnitude'].median():.0f}, "
                 f"max={prob_df['answer_magnitude'].max():.0f}")

    # Near-miss and coherence per run
    lines.append("\n--- Response quality by run ---")
    lines.append(f"{'Run':<20} {'Marker%':>8} {'NearMiss%':>10} {'Consist':>8} {'Gibber%':>8}")
    for run in RUNS:
        sub = resp_df[resp_df["run"] == run]
        lines.append(
            f"{RUN_LABELS[run]:<20} {sub['marker_rate'].mean()*100:>7.1f}% "
            f"{sub['has_near_miss'].mean()*100:>9.1f}% "
            f"{sub['consistency'].mean():>7.2f} "
            f"{(sub['gibberish_count'] > 0).mean()*100:>7.1f}%"
        )

    # Cross-run transitions
    lines.append("\n--- Cross-run transitions (pass@8 vs baseline) ---")
    baseline_pass8 = resp_df.loc[resp_df["run"] == "baseline"].set_index("idx")["pass8"]
    for run in ["separate_a", "separate_b", "combined_ab"]:
        run_pass8 = resp_df.loc[resp_df["run"] == run].set_index("idx")["pass8"]
        common = baseline_pass8.index.intersection(run_pass8.index)
        gained = ((~baseline_pass8.loc[common]) & run_pass8.loc[common]).sum()
        lost = (baseline_pass8.loc[common] & (~run_pass8.loc[common])).sum()
        lines.append(f"  {RUN_LABELS[run]:<20s}: gained={gained}, lost={lost}, net={gained-lost:+d}")

    # Failure mode comparison
    lines.append("\n--- Failure mode % (D9 taxonomy) ---")
    cats = ["no_answer", "format_only", "arithmetic_error", "large_error", "gibberish"]
    header = f"{'Run':<20}" + "".join(f"{c:>15s}" for c in cats)
    lines.append(header)
    for run in RUNS:
        vals = "".join(
            f"{processed['runs'][run]['mistake_pcts'].get(c, 0):>14.1f}%" for c in cats
        )
        lines.append(f"{RUN_LABELS[run]:<20}{vals}")

    text = "\n".join(lines)
    with open(os.path.join(out, "summary.txt"), "w") as f:
        f.write(text)
    print(text)


def table_interesting_problems(prob_df: pd.DataFrame, resp_df: pd.DataFrame,
                               eval_data: dict, questions: list[dict], out: str):
    """Find and save interesting problem examples."""
    lines = []
    lines.append("=" * 80)
    lines.append("INTERESTING PROBLEM EXAMPLES")
    lines.append("=" * 80)

    baseline_df = resp_df[resp_df["run"] == "baseline"].set_index("idx")
    sep_a_df = resp_df[resp_df["run"] == "separate_a"].set_index("idx")

    # 1. Problems gained by format reward (A) — failed baseline, solved by sep_a
    lines.append("\n--- Problems GAINED by Format reward (failed baseline pass@8, solved sep_a) ---")
    gained_mask = (~baseline_df["pass8"]) & sep_a_df.reindex(baseline_df.index)["pass8"]
    gained_idx = gained_mask[gained_mask].index.tolist()[:5]
    for idx in gained_idx:
        q = questions[idx]
        lines.append(f"\n  Problem {idx}: {q['question'][:150]}...")
        lines.append(f"  Gold answer: {prob_df.loc[prob_df['idx']==idx, 'gold_num_str'].values[0]}")
        # Show baseline first response
        bl_resp = eval_data["baseline"][idx]["responses"][0]
        lines.append(f"  Baseline response (first 150): {bl_resp['completion'][:150]}")
        sa_resp = eval_data["separate_a"][idx]["responses"][0]
        lines.append(f"  Sep_A response (first 150): {sa_resp['completion'][:150]}")

    # 2. Problems LOST by format reward
    lines.append("\n\n--- Problems LOST by Format reward (solved baseline, failed sep_a) ---")
    lost_mask = baseline_df["pass8"] & (~sep_a_df.reindex(baseline_df.index)["pass8"])
    lost_idx = lost_mask[lost_mask].index.tolist()[:5]
    for idx in lost_idx:
        q = questions[idx]
        lines.append(f"\n  Problem {idx}: {q['question'][:150]}...")
        lines.append(f"  Gold answer: {prob_df.loc[prob_df['idx']==idx, 'gold_num_str'].values[0]}")

    # 3. Hardest problems (no run solves, pass@8=0 across all)
    lines.append("\n\n--- Hardest problems (no run solves pass@8) ---")
    hard_mask = prob_df["n_runs_pass8"] == 0
    hard_idx = prob_df.loc[hard_mask, "idx"].values[:5]
    for idx in hard_idx:
        q = questions[idx]
        steps = prob_df.loc[prob_df["idx"]==idx, "n_steps"].values[0]
        lines.append(f"\n  Problem {idx} ({steps} steps): {q['question'][:150]}...")
        lines.append(f"  Gold answer: {prob_df.loc[prob_df['idx']==idx, 'gold_num_str'].values[0]}")

    # 4. Easiest problems (all 4 runs solve pass@1)
    lines.append("\n\n--- Easiest problems (all 4 runs solve pass@1) ---")
    easy_mask = prob_df["n_runs_pass1"] == 4
    easy_idx = prob_df.loc[easy_mask, "idx"].values[:5]
    for idx in easy_idx:
        q = questions[idx]
        steps = prob_df.loc[prob_df["idx"]==idx, "n_steps"].values[0]
        lines.append(f"\n  Problem {idx} ({steps} steps): {q['question'][:150]}...")
        lines.append(f"  Gold answer: {prob_df.loc[prob_df['idx']==idx, 'gold_num_str'].values[0]}")

    # 5. High near-miss problems (close but wrong)
    lines.append("\n\n--- Near-miss problems (baseline, min relative error < 5%) ---")
    bl_nm = resp_df[(resp_df["run"] == "baseline") & (resp_df["min_rel_err"] < 0.05) & (~resp_df["pass8"])]
    nm_idx = bl_nm.sort_values("min_rel_err")["idx"].values[:5]
    for idx in nm_idx:
        q = questions[idx]
        gold = prob_df.loc[prob_df["idx"]==idx, "gold_num_str"].values[0]
        bl_row = bl_nm[bl_nm["idx"] == idx].iloc[0]
        lines.append(f"\n  Problem {idx}: {q['question'][:150]}...")
        lines.append(f"  Gold: {gold}, closest pred rel_err: {bl_row['min_rel_err']:.4f}")
        # Show the near-miss prediction
        for r in eval_data["baseline"][idx]["responses"]:
            if r["parseable"] and not r["correct"]:
                lines.append(f"  Predicted: {r['pred_num']} | {r['completion'][:100]}")
                break

    text = "\n".join(lines)
    with open(os.path.join(out, "interesting_problems.txt"), "w") as f:
        f.write(text)
    print(text)


def analysis_question_alignment(eval_data: dict, questions: list[dict], out: str):
    """Critical analysis: does the model actually solve the given question?

    Checks whether model responses relate to the input question by measuring
    proper noun overlap. Also computes a random-collision baseline to determine
    if 'correct' answers are genuine or lucky number matches.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("QUESTION-RESPONSE ALIGNMENT ANALYSIS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Do correct responses actually solve the given question, or do they")
    lines.append("solve a different problem that happens to produce the same number?")
    lines.append("")

    for run in RUNS:
        samples = eval_data[run]

        # 1. Noun overlap check
        aligned = 0
        misaligned = 0
        total_correct = 0
        for s in samples:
            for r in s["responses"]:
                if r["correct"]:
                    total_correct += 1
                    idx = s["idx"]
                    q_nouns = _get_key_nouns(questions[idx]["question"])
                    r_nouns = _get_key_nouns(r["completion"])
                    if q_nouns & r_nouns:
                        aligned += 1
                    else:
                        misaligned += 1

        pct_aligned = aligned / total_correct * 100 if total_correct else 0
        pct_misaligned = misaligned / total_correct * 100 if total_correct else 0
        lines.append(f"--- {RUN_LABELS[run]} ---")
        lines.append(f"  Correct responses: {total_correct}")
        lines.append(f"  Question-aligned (shared proper nouns): {aligned} ({pct_aligned:.1f}%)")
        lines.append(f"  Misaligned (different problem): {misaligned} ({pct_misaligned:.1f}%)")

        # 2. Random collision baseline
        from collections import Counter
        model_answers = Counter()
        for s in samples:
            for r in s["responses"]:
                if r["parseable"]:
                    model_answers[r["pred_num"]] += 1
        total_parseable = sum(model_answers.values())
        expected_correct = 0
        for s in samples:
            gold = s["ref_num"]
            p = model_answers.get(gold, 0) / total_parseable if total_parseable else 0
            expected_correct += p
        expected_pass1 = expected_correct / len(samples) * 100
        actual_pass1 = sum(1 for s in samples if s["responses"][0]["correct"]) / len(samples) * 100
        ratio = actual_pass1 / expected_pass1 if expected_pass1 > 0 else float("inf")
        lines.append(f"  Random collision pass@1: {expected_pass1:.2f}%")
        lines.append(f"  Actual pass@1:           {actual_pass1:.2f}%")
        lines.append(f"  Ratio (actual/random):   {ratio:.1f}x")
        lines.append("")

    # 3. Model answer distribution
    lines.append("--- Model answer distribution (baseline, all parseable) ---")
    bl_samples = eval_data["baseline"]
    model_answers = Counter()
    for s in bl_samples:
        for r in s["responses"]:
            if r["parseable"]:
                model_answers[r["pred_num"]] += 1
    lines.append(f"  Total parseable: {sum(model_answers.values())}")
    lines.append(f"  Distinct values: {len(model_answers)}")
    lines.append(f"  Top 15:")
    for val, count in model_answers.most_common(15):
        lines.append(f"    {val:>8s}: {count:>4d} times")

    # 4. Example: correct but misaligned
    lines.append("")
    lines.append("--- Examples: 'correct' but solving a DIFFERENT problem ---")
    count = 0
    for s in bl_samples:
        if count >= 5:
            break
        r = s["responses"][0]
        if not r["correct"]:
            continue
        idx = s["idx"]
        q_nouns = _get_key_nouns(questions[idx]["question"])
        r_nouns = _get_key_nouns(r["completion"])
        if q_nouns & r_nouns:
            continue
        q_short = questions[idx]["question"][:100].replace("\n", " ")
        r_short = r["completion"][:150].replace("\n", " ")
        lines.append(f"  [{idx}] Question: {q_short}...")
        lines.append(f"       Response: {r_short}...")
        lines.append(f"       Gold={s['ref_num']}, Pred={r['pred_num']} (MATCH but wrong problem)")
        lines.append("")
        count += 1

    # 5. Interpretation
    lines.append("=" * 80)
    lines.append("INTERPRETATION")
    lines.append("=" * 80)
    lines.append("")
    lines.append("The model is NOT solving the given test questions. ~82% of 'correct'")
    lines.append("responses solve a completely different GSM8K-style problem that happens")
    lines.append("to produce the same numeric answer. However, pass@1 is ~9x better than")
    lines.append("random collision, suggesting the model has SOME signal about what number")
    lines.append("to produce (possibly from answer magnitude cues in the question).")
    lines.append("")
    lines.append("This is a form of reward hacking: the binary correctness reward only")
    lines.append("checks if #### <number> matches gold. The model learned to generate")
    lines.append("GSM8K-style solutions producing specific numbers, without conditioning")
    lines.append("on the actual input question. The format reward (A) increases pass@1")
    lines.append("primarily by making more responses parseable (#### present), not by")
    lines.append("improving reasoning — the alignment rate stays ~82% misaligned.")

    text = "\n".join(lines)
    with open(os.path.join(out, "alignment_analysis.txt"), "w") as f:
        f.write(text)
    print(text)


def fig_alignment(eval_data: dict, questions: list[dict], out: str):
    """Figure 1: baseline-only alignment rate and random collision comparison.

    Shows only the RL baseline — reward runs belong in Results, not EDA.
    Styled to match produce.py palette (serif font, clean spines).
    """
    plt.rcParams.update({
        "font.size": 9,
        "font.family": "serif",
        "lines.linewidth": 1.0,
        "axes.linewidth": 0.5,
        "mathtext.fontset": "stix",
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })

    run = "baseline"
    samples = eval_data[run]

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.5))

    # 1. Alignment rate (single bar)
    ax = axes[0]
    aligned = 0
    total = 0
    for s in samples:
        for r in s["responses"]:
            if r["correct"]:
                total += 1
                q_nouns = _get_key_nouns(questions[s["idx"]]["question"])
                r_nouns = _get_key_nouns(r["completion"])
                if q_nouns & r_nouns:
                    aligned += 1
    aligned_pct = aligned / total * 100 if total else 0
    misaligned_pct = 100 - aligned_pct

    bars = ax.bar(["Aligned", "Misaligned"], [aligned_pct, misaligned_pct],
                  color=["#4895ef", "#f72585"], edgecolor="white", linewidth=0.3, width=0.5)
    ax.set_ylabel("% of correct responses")
    ax.set_title("(a) Question-response alignment\n(RL baseline)")
    ax.set_ylim(0, 100)
    for bar, v in zip(bars, [aligned_pct, misaligned_pct]):
        ax.text(bar.get_x() + bar.get_width()/2, v + 2, f"{v:.1f}%", ha="center", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # 2. Actual vs random collision pass@1 (single pair)
    ax = axes[1]
    model_answers = Counter()
    for s in samples:
        for r in s["responses"]:
            if r["parseable"]:
                model_answers[r["pred_num"]] += 1
    total_p = sum(model_answers.values())
    random_rate = sum(model_answers.get(s["ref_num"], 0) / total_p if total_p else 0
                      for s in samples) / len(samples) * 100
    actual_rate = sum(1 for s in samples if s["responses"][0]["correct"]) / len(samples) * 100

    bars = ax.bar(["Actual Pass@1", "Random collision"], [actual_rate, random_rate],
                  color=["#0466c8", "#9b2226"], edgecolor="white", linewidth=0.3, width=0.5)
    ax.set_ylabel("Pass@1 (%)")
    ax.set_title("(b) Actual vs random baseline\n(RL baseline)")
    for bar, v in zip(bars, [actual_rate, random_rate]):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.3, f"{v:.1f}%", ha="center", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig_alignment.pdf"))
    plt.close()


def _get_key_nouns(text: str) -> set[str]:
    """Extract proper nouns (capitalized words not at sentence start)."""
    words = text.split()
    nouns = set()
    for i, w in enumerate(words):
        clean = re.sub(r"[^a-zA-Z]", "", w)
        if clean and clean[0].isupper() and len(clean) > 2 and i > 0:
            nouns.add(clean.lower())
    return nouns


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GSM8K EDA across RL runs")
    parser.add_argument("--output-dir", default="a4/p4/results/eda")
    parser.add_argument("--eval-dir", default=EVAL_DIR)
    parser.add_argument("--processed", default=PROCESSED_PATH)
    args = parser.parse_args()

    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    print("[eda] Loading data...")
    questions = load_gsm8k_questions()
    eval_data = load_eval_data(args.eval_dir)
    processed = load_processed(args.processed)

    print("[eda] Extracting problem features...")
    prob_df = extract_problem_features(questions)

    print("[eda] Extracting response features...")
    resp_df = extract_response_features(eval_data)

    print("[eda] Generating figures...")
    prob_df = fig_difficulty_tiers(prob_df, resp_df, out)
    fig_complexity_vs_difficulty(prob_df, out)
    fig_topic_breakdown(prob_df, out)
    fig_failure_modes_by_run(resp_df, eval_data, processed, out)
    fig_coherence_analysis(resp_df, out)
    fig_near_miss_analysis(resp_df, out)
    fig_consistency(resp_df, out)
    fig_cross_run_transitions(resp_df, out)
    fig_topic_x_run(prob_df, resp_df, out)
    fig_step_count_pass_rate(prob_df, resp_df, out)

    print("[eda] Analyzing question-response alignment...")
    analysis_question_alignment(eval_data, questions, out)
    fig_alignment(eval_data, questions, out)

    print("[eda] Writing summary tables...")
    table_summary(prob_df, resp_df, processed, out)
    table_interesting_problems(prob_df, resp_df, eval_data, questions, out)

    # Save dataframes for further analysis
    prob_df.to_csv(os.path.join(out, "problem_features.csv"), index=False)
    resp_df.to_csv(os.path.join(out, "response_features.csv"), index=False)

    print(f"\n[eda] Done. {len(os.listdir(out))} files written to {out}/")


if __name__ == "__main__":
    main()
