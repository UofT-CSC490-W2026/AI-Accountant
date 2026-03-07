"""Generate all P3 plots and tables from pulled data files."""

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# ── Paths ──
RESULTS = Path(__file__).resolve().parent.parent / "results"
FIGURES = RESULTS / "figures"
FIGURES.mkdir(exist_ok=True)

with open(RESULTS / "local_data.json") as f:
    local = json.load(f)
with open(RESULTS / "wandb_history.json") as f:
    wb_hist = json.load(f)
with open(RESULTS / "wandb_data.json") as f:
    wb_runs = json.load(f)
with open(RESULTS / "modal_data.json") as f:
    modal = json.load(f)

# ── Helpers ──
def get_custom_eval(tag, step):
    for e in local["custom_evals"]:
        if e["model_tag"] == tag and e["step"] == step:
            return e
    return None

def get_core(tag, step):
    for e in local["core_csvs"]:
        if e["model_tag"] == tag and e["step"] == step:
            return e
    return None

def get_wb_run(display_name):
    """Look up by config.run.value (e.g. 'p3-baseline-full'), preferring canonical (Mar 3) runs."""
    # Canonical runs have log_every in config (Mar 3 pipeline with --log-every patch)
    matches = [r for r in wb_runs
               if r["config"].get("run", {}).get("value") == display_name]
    # Prefer the one with log_every (canonical)
    for m in matches:
        if "log_every" in m["config"]:
            return m
    return matches[0] if matches else None

def bucket_midpoints(ev):
    return [(b["position_start"] + b["position_end"]) / 2 for b in ev["buckets"]]

def bucket_ce(ev):
    return [b["mean_cross_entropy"] for b in ev["buckets"]]

# Canonical runs
SHORT_RUN = "p3-baseline-short"   # mpaiemt0
FULL_RUN = "p3-baseline-full"     # wy8sw0zf
EXT_RUN = "p3-baseline-extended"  # woxwtud7

COLORS = {
    "short": "#d62728",    # red
    "extended": "#2ca02c", # green
    "full": "#1f77b4",     # blue
}

# ═══════════════════════════════════════════════════════════════════
# PLOT 1: Per-position cross-entropy (main figure)
# 3 lines: short@1433, extended@1933, full@1433
# ═══════════════════════════════════════════════════════════════════
def plot_per_position_ce():
    fig, ax = plt.subplots(figsize=(10, 5))

    short = get_custom_eval("pico-short", 1433)
    ext = get_custom_eval("pico-short", 1933)
    full = get_custom_eval("pico-full", 1433)

    x = bucket_midpoints(short)

    ax.plot(x, bucket_ce(short), "o-", color=COLORS["short"],
            label="Short (seq_len=512, step 1433)", markersize=5)
    ax.plot(x, bucket_ce(ext), "s-", color=COLORS["extended"],
            label="Extended (512→2048, step 1933)", markersize=5)
    ax.plot(x, bucket_ce(full), "^-", color=COLORS["full"],
            label="Full (seq_len=2048, step 1433)", markersize=5)

    ax.axvline(x=512, color="gray", linestyle="--", alpha=0.7, label="Training boundary (512)")
    ax.set_xlabel("Token Position")
    ax.set_ylabel("Mean Cross-Entropy (nats)")
    ax.set_title("Per-Position Cross-Entropy on PG19 (3 Checkpoints)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 2048)

    fig.tight_layout()
    fig.savefig(FIGURES / "per_position_ce.png", dpi=150)
    plt.close(fig)
    print("✓ per_position_ce.png")


# ═══════════════════════════════════════════════════════════════════
# PLOT 2: Recovery evolution — per-position CE at each extension step
# ═══════════════════════════════════════════════════════════════════
def plot_recovery_evolution():
    fig, ax = plt.subplots(figsize=(10, 5))

    # Extension checkpoints: 1433 (pre-extension), 1450, 1500, ..., 1933
    ext_steps = sorted(set(
        e["step"] for e in local["custom_evals"] if e["model_tag"] == "pico-short"
    ))

    cmap = plt.cm.viridis
    norm = plt.Normalize(vmin=min(ext_steps), vmax=max(ext_steps))

    for step in ext_steps:
        ev = get_custom_eval("pico-short", step)
        x = bucket_midpoints(ev)
        alpha = 0.4 if step == 1433 else 0.8
        lw = 1.5 if step in (1433, 1933) else 0.9
        ax.plot(x, bucket_ce(ev), "-", color=cmap(norm(step)),
                alpha=alpha, linewidth=lw, label=f"step {step}")

    # Full baseline for reference
    full = get_custom_eval("pico-full", 1433)
    ax.plot(bucket_midpoints(full), bucket_ce(full), "k--", linewidth=1.5,
            alpha=0.6, label="Full baseline")

    ax.axvline(x=512, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Token Position")
    ax.set_ylabel("Mean Cross-Entropy (nats)")
    ax.set_title("Recovery Evolution: Per-Position CE During Context Extension")
    ax.legend(fontsize=7, ncol=3, loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 2048)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, label="Training Step", pad=0.02)

    fig.tight_layout()
    fig.savefig(FIGURES / "recovery_evolution.png", dpi=150)
    plt.close(fig)
    print("✓ recovery_evolution.png")


# ═══════════════════════════════════════════════════════════════════
# PLOT 3: Training loss curves (from W&B history)
# ═══════════════════════════════════════════════════════════════════
def plot_training_curves():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    for run_name, label, color in [
        (SHORT_RUN, "Short (seq_len=512)", COLORS["short"]),
        (FULL_RUN, "Full (seq_len=2048)", COLORS["full"]),
        (EXT_RUN, "Extended (512→2048)", COLORS["extended"]),
    ]:
        h = wb_hist[run_name]
        # Train loss
        tl = [(r["step"], r["train_loss"]) for r in h["train_loss"]]
        tl.sort()
        ax1.plot([t[0] for t in tl], [t[1] for t in tl], "-", color=color,
                 label=label, linewidth=1.5)
        # Val BPB
        vb = [(r["step"], r["val_bpb"]) for r in h["val_bpb"]]
        vb.sort()
        ax2.plot([v[0] for v in vb], [v[1] for v in vb], "-", color=color,
                 label=label, linewidth=1.5)

    for ax, title, ylabel in [
        (ax1, "Training Loss", "Loss (nats)"),
        (ax2, "Validation BPB", "Bits Per Byte"),
    ]:
        ax.set_xlabel("Step")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.axvline(x=1433, color="gray", linestyle=":", alpha=0.4)

    fig.tight_layout()
    fig.savefig(FIGURES / "training_curves.png", dpi=150)
    plt.close(fig)
    print("✓ training_curves.png")


# ═══════════════════════════════════════════════════════════════════
# PLOT 4: BPB + CORE recovery during extension
# ═══════════════════════════════════════════════════════════════════
def plot_bpb_core_recovery():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    # Val BPB during extension (from W&B)
    ext_bpb = wb_hist[EXT_RUN]["val_bpb"]
    ext_bpb.sort(key=lambda r: r["step"])
    steps_bpb = [r["step"] for r in ext_bpb]
    vals_bpb = [r["val_bpb"] for r in ext_bpb]

    # Full baseline BPB
    full_run = get_wb_run("p3-baseline-full")
    full_bpb = full_run["summary"]["val/bpb"]

    ax1.plot(steps_bpb, vals_bpb, "o-", color=COLORS["extended"], label="Extended", markersize=4)
    ax1.axhline(y=full_bpb, color=COLORS["full"], linestyle="--", label=f"Full baseline ({full_bpb:.4f})")
    ax1.set_xlabel("Step")
    ax1.set_ylabel("Validation BPB")
    ax1.set_title("BPB Recovery During Extension")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # CORE during extension (from local data)
    core_ext = [(e["step"], e["core_score"])
                for e in local["core_csvs"] if e["model_tag"] == "pico-short"]
    core_ext.sort()
    full_core = get_core("pico-full", 1433)["core_score"]

    ax2.plot([c[0] for c in core_ext], [c[1] for c in core_ext],
             "o-", color=COLORS["extended"], label="Extended", markersize=4)
    ax2.axhline(y=full_core, color=COLORS["full"], linestyle="--",
                label=f"Full baseline ({full_core:.4f})")
    ax2.set_xlabel("Step")
    ax2.set_ylabel("CORE Score")
    ax2.set_title("CORE Recovery During Extension")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(FIGURES / "bpb_core_recovery.png", dpi=150)
    plt.close(fig)
    print("✓ bpb_core_recovery.png")


# ═══════════════════════════════════════════════════════════════════
# TABLE 1: BPB comparison (printed as markdown)
# ═══════════════════════════════════════════════════════════════════
def table_bpb():
    rows = []
    for name, label in [
        ("p3-baseline-short", "Short (512, step 1433)"),
        ("p3-baseline-extended", "Extended (512→2048, step 1933)"),
        ("p3-baseline-full", "Full (2048, step 1433)"),
    ]:
        r = get_wb_run(name)
        s = r["summary"]
        rows.append((label, s.get("train/loss", "—"), s.get("val/bpb", "—")))

    lines = []
    lines.append("| Checkpoint | Train Loss | Val BPB |")
    lines.append("|------------|-----------|---------|")
    for label, tl, vb in rows:
        tl_s = f"{tl:.4f}" if isinstance(tl, float) else tl
        vb_s = f"{vb:.4f}" if isinstance(vb, float) else vb
        lines.append(f"| {label} | {tl_s} | {vb_s} |")

    table = "\n".join(lines)
    (FIGURES / "table_bpb.md").write_text(table + "\n")
    print("✓ table_bpb.md")
    print(table)


# ═══════════════════════════════════════════════════════════════════
# TABLE 2: CORE comparison (aggregate + per-task for endpoints)
# ═══════════════════════════════════════════════════════════════════
def table_core():
    ext = get_core("pico-short", 1933)
    full = get_core("pico-full", 1433)

    # Get all task names from full baseline
    task_names = [t["task"] for t in full["tasks"]]

    lines = []
    lines.append("| Task | Extended (1933) | Full (1433) |")
    lines.append("|------|----------------|-------------|")

    # Aggregate
    lines.append(f"| **CORE (aggregate)** | **{ext['core_score']:.4f}** | **{full['core_score']:.4f}** |")

    # Per-task
    ext_tasks = {t["task"]: t for t in ext["tasks"]}
    full_tasks = {t["task"]: t for t in full["tasks"]}
    for task in task_names:
        e_acc = ext_tasks.get(task, {}).get("accuracy", "—")
        f_acc = full_tasks.get(task, {}).get("accuracy", "—")
        e_s = f"{e_acc:.4f}" if isinstance(e_acc, float) else e_acc
        f_s = f"{f_acc:.4f}" if isinstance(f_acc, float) else f_acc
        lines.append(f"| {task} | {e_s} | {f_s} |")

    table = "\n".join(lines)
    (FIGURES / "table_core.md").write_text(table + "\n")
    print("✓ table_core.md")
    print(table)


# ═══════════════════════════════════════════════════════════════════
# TABLE 3: Summary comparison (all metrics, 3 checkpoints)
# ═══════════════════════════════════════════════════════════════════
def table_summary():
    short_ev = get_custom_eval("pico-short", 1433)
    ext_ev = get_custom_eval("pico-short", 1933)
    full_ev = get_custom_eval("pico-full", 1433)

    short_run = get_wb_run("p3-baseline-short")
    ext_run = get_wb_run("p3-baseline-extended")
    full_run = get_wb_run("p3-baseline-full")

    ext_core = get_core("pico-short", 1933)
    full_core = get_core("pico-full", 1433)

    # CE beyond 512 (avg of buckets 4-15)
    def ce_beyond_512(ev):
        return np.mean([b["mean_cross_entropy"] for b in ev["buckets"][4:]])
    def ce_within_512(ev):
        return np.mean([b["mean_cross_entropy"] for b in ev["buckets"][:4]])

    lines = []
    lines.append("| Metric | Short (1433) | Extended (1933) | Full (1433) |")
    lines.append("|--------|-------------|----------------|-------------|")
    lines.append(f"| Val BPB | {short_run['summary']['val/bpb']:.4f} | {ext_run['summary']['val/bpb']:.4f} | {full_run['summary']['val/bpb']:.4f} |")
    lines.append(f"| Train Loss | {short_run['summary']['train/loss']:.4f} | {ext_run['summary']['train/loss']:.4f} | {full_run['summary']['train/loss']:.4f} |")
    lines.append(f"| PG19 Aggregate CE | {short_ev['aggregate_cross_entropy']:.4f} | {ext_ev['aggregate_cross_entropy']:.4f} | {full_ev['aggregate_cross_entropy']:.4f} |")
    lines.append(f"| PG19 Aggregate PPL | {short_ev['aggregate_perplexity']:.2f} | {ext_ev['aggregate_perplexity']:.2f} | {full_ev['aggregate_perplexity']:.2f} |")
    lines.append(f"| CE (pos 0–512) | {ce_within_512(short_ev):.4f} | {ce_within_512(ext_ev):.4f} | {ce_within_512(full_ev):.4f} |")
    lines.append(f"| CE (pos 512–2048) | {ce_beyond_512(short_ev):.4f} | {ce_beyond_512(ext_ev):.4f} | {ce_beyond_512(full_ev):.4f} |")
    lines.append(f"| CORE | N/A (RoPE limit) | {ext_core['core_score']:.4f} | {full_core['core_score']:.4f} |")

    table = "\n".join(lines)
    (FIGURES / "table_summary.md").write_text(table + "\n")
    print("✓ table_summary.md")
    print(table)


# ═══════════════════════════════════════════════════════════════════
# TABLE 4: Cost report (GPU-hours)
# ═══════════════════════════════════════════════════════════════════
def table_cost():
    apps = modal["apps"]

    lines = []
    lines.append("| App ID | GPU-Hours | Cost ($) | First Interval |")
    lines.append("|--------|----------|---------|----------------|")

    for aid, info in sorted(apps.items(), key=lambda x: -x[1]["gpu_hours"]):
        hours = info["gpu_hours"]
        cost = info["cost_usd"]
        earliest = min(info["intervals"])
        lines.append(f"| …{aid[-8:]} | {hours:.3f} | {cost:.2f} | {earliest[:13]} |")

    lines.append(f"| **Total ({len(apps)} apps)** | **{modal['total_gpu_hours']:.2f}** | **{modal['total_cost_usd']:.2f}** | |")

    table = "\n".join(lines)
    (FIGURES / "table_cost.md").write_text(table + "\n")
    print("✓ table_cost.md")
    print(table)


# ═══════════════════════════════════════════════════════════════════
# Run all
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("Generating plots...")
    print("=" * 60)
    plot_per_position_ce()
    plot_recovery_evolution()
    plot_training_curves()
    plot_bpb_core_recovery()

    print()
    print("=" * 60)
    print("Generating tables...")
    print("=" * 60)
    table_bpb()
    print()
    table_core()
    print()
    table_summary()
    print()
    table_cost()

    print()
    print(f"All outputs in: {FIGURES}")
