# Assets Research

## 1. Formulation

### Motivation

This research defines what output artifacts (tables, figures, plots) the writeup needs, how they should be formatted, and what conventions to follow. The asset design must render:

- Everything specified in **design-metrics.md** (what to measure)
- Everything specified in **design-ablation.md** (what to compare)

And directly satisfy:
- **R11**: Create visualizations illustrating mistake type differences
- **R12**: Summary table of all results

### What Must Be Rendered

From **design-metrics.md** (9 metrics + 2 derived):
- Training-time metrics: mean reward curves, per-component reward curves, sequence length curves — all per run
- Post-training metrics: Pass@1, Pass@8, extraction failure rate, per-category error counts/percentages, net problem delta — all per run
- Derived: Pass@8−Pass@1 gap, error distribution delta

From **design-ablation.md** (15 comparisons in 3 tiers):
- Tier 1 (C1-C9): Pairwise comparison results → ablation table
- Tier 2 (C10-C12): Synergy detection, per-component curves, problem overlap
- Tier 3 (C13-C15): Error distribution comparisons, stacked bars, delta bars

### Research Questions

**RQ1: What table formats best present multi-run metric comparisons?**

*Grounding*: R12 requires a summary table of all results. design-ablation.md defines 6 runs × multiple metrics. We need to know how RL/NLP papers typically format ablation tables — column layout, highlighting, delta notation.

*Sub-questions*:
- How do papers with 5-10 runs and 3-5 metrics format their main results table?
- Do papers use absolute values, deltas from baseline, or both?
- How are best results highlighted (bold, underline, color)?
- What column ordering is standard (runs as rows or columns)?

**RQ2: What visualizations best show mistake type shifts across reward configurations?**

*Grounding*: R11 requires visualizations of mistake differences. design-ablation.md C13-C15 define error distribution comparisons between Baseline and reward-modified runs. We need chart types that effectively show categorical distribution shifts.

*Sub-questions*:
- What chart types are standard for comparing categorical distributions across conditions (stacked bar, grouped bar, heatmap)?
- How do papers visualize per-problem correctness changes (Sankey/alluvial, confusion matrix, Venn diagram)?
- What color schemes and labeling conventions make error category charts readable?

**RQ3: What output formats work for integration into a LaTeX/PDF writeup?**

*Grounding*: The final deliverable is a writeup (likely PDF). Assets need to be in formats that integrate cleanly — vector graphics for plots, LaTeX tabular for tables, or PNG at sufficient resolution.

*Sub-questions*:
- What resolution/format do NLP papers use for figures (PNG, PDF, SVG)?
- Do papers generate tables as LaTeX tabular directly or as images?
- What tools/libraries produce publication-quality figures for NLP papers (matplotlib, seaborn, plotly)?

**RQ4: How do papers present training dynamics (reward curves) across multiple runs?**

*Grounding*: design-ablation.md C11 requires per-component reward curves from training. We have 6 runs, each with mean reward, per-component reward, and sequence length over ~8 checkpoints. Need to show these compactly.

*Sub-questions*:
- Do papers overlay all runs on one plot or use small multiples (subplots)?
- How are per-component rewards shown in combined runs (separate axes, stacked, overlaid)?
- What x-axis convention is used (step number, epoch, tokens seen)?

### Search Strategy

**Sources to consult**:
1. NLP/RL papers with multi-run ablation tables (especially GSM8k, MATH papers)
2. Visualization best practices for categorical comparisons
3. LaTeX/matplotlib formatting guides for publication figures

**Search terms**:
- "ablation table format NLP paper multi-run comparison"
- "error category visualization comparison stacked bar chart NLP"
- "training curve reward plot multiple runs RL paper"
- "matplotlib publication quality figure NLP LaTeX"
