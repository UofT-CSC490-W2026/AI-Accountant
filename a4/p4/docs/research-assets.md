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

---

## 2. Results

### RQ1: Table formats for multi-run metric comparisons

**Standard ablation table format**: NLP/RL papers with 5-10 runs and 3-5 metrics consistently use the same structure:
- **Rows = runs/configurations**, columns = metrics. This is nearly universal — AceMath (ACL 2025), FOVER (2025), OpenMathInstruct-1 (NeurIPS 2024), GSM-Symbolic (ICLR 2025) all follow this pattern.
- **Bold for best result** per column. This is the dominant convention. Some papers also underline second-best.
- **Absolute values** are standard for headline metrics (Pass@1, Pass@8). Delta columns (Δ vs baseline) are used as supplementary columns, not replacements — especially useful for ablation tables where the reader needs to see both the magnitude and the change.
- **Mean ± std** when multiple seeds are available. Since we have single runs, we report point values without error bars. This is acceptable — GSM-Symbolic (ICLR 2025) reports single-run results with appropriate caveats.
- **`booktabs`** package (LaTeX) for clean horizontal rules (`\toprule`, `\midrule`, `\bottomrule`). No vertical lines.
- **"w/o" notation** for ablation variants (e.g., "w/o Format Compliance"). Our runs use additive framing ("+ Format Compliance"), which is equally standard.

**Our table structure** (for R12 summary table):

```
Rows: Baseline, +A (Format), +B (Proximity), +C, +D, Combined
Cols: Pass@1, Pass@8, Gap, Extraction Fail%, Net Δ (gained/lost)
```

Best values bolded per column. Footnote noting single-run limitation.

**Sources**:
- [AceMath: Advancing Frontier Math Reasoning](https://aclanthology.org/2025.findings-acl.206.pdf) — Tables 5-7 ablation format
- [FOVER: Generalizable Process Reward Models](https://arxiv.org/pdf/2505.15960) — Table 3 Best-of-K comparison
- [GSM-Symbolic (ICLR 2025)](https://arxiv.org/pdf/2410.05229) — Table 1 multi-model results
- [OpenMathInstruct-1 (NeurIPS 2024)](https://proceedings.neurips.cc/paper_files/paper/2024/file/3d5aa9a7ce28cdc710fbd044fd3610f3-Paper-Datasets_and_Benchmarks_Track.pdf) — Table 3 ablation format

### RQ2: Visualizations for mistake type shifts

**Stacked bar charts** for part-to-whole composition:
- Best for showing "what fraction of errors is each category" across runs. Each bar = one run, segments = error categories. Allows comparing both total error count and composition.
- Limitation: only the bottom segment shares a common baseline, making precise comparison of middle segments difficult. Mitigated by keeping to ≤5 segments (our D9 taxonomy has 6 categories — acceptable).
- **Inverting stacked bars** (common baseline at center) improve comparison for non-bottom segments, but are less familiar to readers.

**Grouped bar charts** for direct category comparison:
- Better when the primary question is "how does category X change across runs" — each cluster = one error category, bars within = runs. Easier to compare individual categories but loses part-to-whole context.
- Best for our C14 comparisons (Baseline vs each Separate run, per error category).

**Delta bar charts** for showing shifts:
- Horizontal bars showing (Run X % − Baseline %) per error category. Positive = category grew, negative = shrank. Clean way to show C13/C14 changes.
- Most compact format for "what changed" questions.

**Per-problem correctness visualization**:
- **Alluvial/Sankey diagrams** can show flow of problems between correct/incorrect states across runs. Useful for C12 (problem overlap analysis) but may be overcomplicated for 6 runs.
- **Simple gained/lost counts** (bar chart or table) are more practical for our case — show problems gained and lost separately for each run vs Baseline.
- **Heatmaps** (problem × run, colored by correct/incorrect) are effective when there are natural groupings of problems but become unreadable at 1319 problems. Not practical for our case.

**Color conventions**:
- Use a qualitative palette (e.g., matplotlib's `Set2` or `tab10`) for error categories — distinct, colorblind-friendly.
- For delta charts: green/blue for improvement, red/orange for degradation.
- Keep consistent colors for the same error category across all figures.

**Recommendation for our assets**:
1. **Stacked bar chart** — error distribution composition per run (C13, C15)
2. **Delta bar chart** — error category % change vs Baseline (C14, C15)
3. **Gained/lost table or bar** — per-problem delta counts (C12)

**Sources**:
- [Stacked Bar Chart Guide (Atlassian)](https://www.atlassian.com/data/charts/stacked-bar-chart-complete-guide)
- [Grouped Bar Chart Guide (Atlassian)](https://www.atlassian.com/data/charts/grouped-bar-chart-complete-guide)
- [Efficacy of stacked bar charts (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2468502X18300287)
- [CrossCheck: Rapid, Reproducible Model Evaluation (ACL DASH 2021)](https://aclanthology.org/2021.dash-1.13.pdf)

### RQ3: Output formats for LaTeX/PDF integration

**Figure formats**:
- **PDF** is the preferred vector format for figures in LaTeX papers compiled with `pdflatex`. Infinitely zoomable, small file size for line plots. This is the standard in NLP venues (ACL, EMNLP, NeurIPS).
- **SVG** is useful as an intermediate format (editable in Inkscape/Illustrator) but must be converted to PDF for LaTeX inclusion.
- **PNG at 300+ DPI** is acceptable for raster content (photos, screenshots) but should be avoided for line plots and charts — vector formats are always preferred.
- For scatter plots with many points, use `rasterized=True` in matplotlib to rasterize only the data points while keeping axes/labels as vectors.

**Table formats**:
- **LaTeX `tabular`** generated directly (not as images). This is universal practice — tables are typeset text, not figures.
- Use `booktabs` package for professional rules. Never use vertical lines.
- Generate LaTeX source programmatically (Python script) so tables update automatically when data changes.

**Tooling**:
- **matplotlib** is the standard for publication-quality figures in ML/NLP. Provides full control over every element. Use `plt.savefig('fig.pdf', bbox_inches='tight')` for PDF output.
- **seaborn** builds on matplotlib, useful for statistical plots (heatmaps, violin plots) but matplotlib gives finer control for custom figures.
- **SciencePlots** library provides preconfigured themes for academic papers, though custom `rcParams` can achieve the same.
- Key `rcParams` for papers: font size ~9pt, line width ~1.0pt, font family matching document (Times/Computer Modern), `mathtext.fontset: 'stix'` for consistent math rendering.

**Recommended setup**:
```python
import matplotlib.pyplot as plt
plt.rcParams.update({
    'font.size': 9,
    'font.family': 'serif',
    'lines.linewidth': 1.0,
    'axes.linewidth': 0.5,
    'mathtext.fontset': 'stix',
    'savefig.dpi': 300,  # for any rasterized elements
    'savefig.bbox': 'tight',
})
```

**Sources**:
- [matplotlib_for_papers (GitHub tutorial)](https://github.com/jbmouret/matplotlib_for_papers)
- [Publication-quality figures with matplotlib (Albert Chen)](https://atchen.me/research/code/data-viz/2022/01/04/plotting-matplotlib-reference.html)
- [Embed matplotlib in LaTeX (jwalton.info)](https://jwalton.info/Embed-Publication-Matplotlib-Latex/)
- [Tips for Academic Figures with Matplotlib](https://allanchain.github.io/blog/post/mpl-paper-tips/)
- [Publication-quality Plots (Bastian Bloessl)](https://www.bastibl.net/publication-quality-plots/)

### RQ4: Training dynamics presentation

**Overlay vs small multiples**:
- **Overlay on one plot** is the standard when comparing the same metric across runs. The CS294-112 (Berkeley Deep RL) plotting handout recommends plotting all runs on the same plot initially, with averages in a thicker/different-color line. This works well for our mean reward curves (6 runs on one plot).
- **Small multiples (subplots)** are better when each run has multiple sub-metrics that would overcrowd a single plot. Recommended for per-component reward curves in the Combined run (original + A + B + C + D components each get a line, which would be 5 lines — manageable in one subplot but could use a 2×3 grid if combined with other runs).
- **Our case**: 6 runs × 1 mean reward = overlay. Combined run × 5 components = separate subplot or dedicated figure.

**Shading and confidence**:
- Standard convention: solid line = mean, shaded region = ±1 std (across seeds). Since we have single runs, no shading is needed — just solid lines with distinct colors/markers per run.
- Use a legend or direct line labels (less clutter than a legend for ≤6 lines).

**X-axis convention**:
- **Training step** is the most common x-axis for RL reward curves. Our runs have ~8 checkpoints at every-60-steps intervals (steps 0, 60, 120, ..., 420, 467). Use step number on x-axis.
- Some papers use "tokens seen" or "gradient updates" — step number is equivalent in our case since batch size is constant.

**Smoothing**:
- Raw reward values fluctuate episode-to-episode. Moving average smoothing is common, but with only ~8 checkpoints we have pre-aggregated means from W&B, so no additional smoothing is needed.

**Key training curve metrics to extract** (from Berkeley handout):
- Asymptotic level (final performance after stabilization)
- Minimum of the curve (how much reward is sacrificed before improvement)
- Trajectory shape (monotonic increase, early spike then plateau, etc.)

**Recommendation for our assets**:
1. **Mean reward overlay** — all 6 runs on one plot, step on x-axis, mean reward on y-axis
2. **Per-component subplot** — Combined run only, 5 component lines on one plot (or small multiples if too crowded)
3. **Sequence length overlay** — all 6 runs on one plot (separate figure from reward)

**Sources**:
- [CS294-112 Deep RL Plotting Handout (Berkeley)](https://rll.berkeley.edu/deeprlcoursesp17/docs/plotting_handout.pdf)
- [Reward Engineering Survey (arXiv:2408.10215)](https://arxiv.org/html/2408.10215v1)
- [Stable Baselines RL Tips](https://stable-baselines.readthedocs.io/en/master/guide/rl_tips.html)
- [Learning Curves (Alexander Fabisch)](https://alexanderfabisch.github.io/learning-curves-2.html)

### Summary: Candidate Asset Types

| Asset | Type | Purpose | Requirement |
|-------|------|---------|-------------|
| Summary results table | LaTeX tabular | All runs × headline metrics | R12 |
| Error distribution stacked bar | matplotlib → PDF | Composition per run | R11, C13, C15 |
| Error delta bar chart | matplotlib → PDF | Category shifts vs Baseline | R11, C14, C15 |
| Mean reward overlay plot | matplotlib → PDF | Training dynamics comparison | C1-C5, C11 |
| Per-component reward plot | matplotlib → PDF | Combined run decomposition | C11, R19 |
| Sequence length overlay | matplotlib → PDF | Training dynamics | C1-C5 |
| Gained/lost table | LaTeX tabular | Per-problem delta counts | C12 |
| Synergy table | LaTeX tabular | Combined vs sum of Separates | C10 |
