# Assets Design

## Asset Inventory

8 artifacts: 3 tables (LaTeX tabular) + 5 figures (matplotlib → PDF).

| ID | Name | Type | Format | Requirement | Comparisons |
|----|------|------|--------|-------------|-------------|
| T1 | Summary results table | Table | LaTeX tabular | R12 | C1-C9 |
| T2 | Gained/lost delta table | Table | LaTeX tabular | R9, R10 | C1-C5 |
| T3 | Synergy analysis table | Table | LaTeX tabular | R10, R13 | C10, C12 |
| F1 | Error distribution stacked bar | Figure | PDF (vector) | R11 | C13, C15 |
| F2 | Error delta bar chart | Figure | PDF (vector) | R11 | C14, C15 |
| F3 | Mean reward overlay | Figure | PDF (vector) | — | C1-C5 |
| F4 | Per-component reward plot | Figure | PDF (vector) | R13, R19 | C11 |
| F5 | Sequence length overlay | Figure | PDF (vector) | — | C1-C5 |

---

## Tables

### T1: Summary Results Table (R12)

**Purpose**: Single table containing all runs and headline metrics. Satisfies R12 ("summary table of all results").

**Schema**:

| Column | Source | Cell value |
|--------|--------|------------|
| Run | D3 | Run name |
| Pass@1 (%) | Eval | `correct_problems / 1319 × 100`, strict extraction |
| Pass@8 (%) | Eval | `problems_with_≥1_correct_in_8 / 1319 × 100` |
| Gap (%) | Derived | `Pass@8 − Pass@1` |
| Extr. Fail (%) | Eval | `responses_without_parseable_answer / total_responses × 100` |
| Δ Pass@1 | Derived | `run_pass@1 − baseline_pass@1`, signed, pp |

**Rows** (fixed order):
1. Baseline
2. + Format Compliance (A)
3. + Numeric Proximity (B)
4. + C (post-P3)
5. + D (post-P3)
6. Combined (all)

**Formatting**:
- `booktabs` rules (`\toprule`, `\midrule`, `\bottomrule`)
- **Bold** best value per column (excluding Δ column)
- Baseline row separated by `\midrule` from reward-modified rows
- Δ column: `+X.X` / `−X.X` format, no bold
- Caption: "Summary of evaluation results across all reward configurations. Best per column in **bold**. Single run per configuration."
- No vertical lines

### T2: Gained/Lost Delta Table (R9, R10)

**Purpose**: Per-problem correctness changes for each run vs Baseline. More robust than aggregate accuracy (per research findings).

**Schema**:

| Column | Source | Cell value |
|--------|--------|------------|
| Run | D3 | Run name (excluding Baseline) |
| Gained | Eval | Count of problems incorrect in Baseline but correct in this run |
| Lost | Eval | Count of problems correct in Baseline but incorrect in this run |
| Net | Derived | `Gained − Lost` |

**Rows**: 5 rows (all non-Baseline runs)

**Formatting**:
- `booktabs` rules
- Gained in regular text, Lost in regular text, Net **bold** if ≥ 26 (>2% = meaningful per significance criteria)
- Caption: "Per-problem correctness changes vs Baseline. Net = Gained − Lost."

### T3: Synergy Analysis Table (R10, R13)

**Purpose**: Decompose Combined run performance into individual contributions. Detect synergy/interference.

**Schema**:

| Column | Source | Cell value |
|--------|--------|------------|
| Metric | — | Row label |
| Sep A Δ | Derived | `Sep_A_pass@1 − Baseline_pass@1` |
| Sep B Δ | Derived | `Sep_B_pass@1 − Baseline_pass@1` |
| Sep C Δ | Derived | `Sep_C_pass@1 − Baseline_pass@1` |
| Sep D Δ | Derived | `Sep_D_pass@1 − Baseline_pass@1` |
| Sum | Derived | `Sep_A_Δ + Sep_B_Δ + Sep_C_Δ + Sep_D_Δ` |
| Combined Δ | Derived | `Combined_pass@1 − Baseline_pass@1` |
| Pattern | Derived | Synergy / Interference / Additive |

**Rows**:
1. Pass@1 (primary)
2. Problems gained (supplementary)

**Pattern assignment**:
- Synergy: Combined Δ > Sum
- Interference: Combined Δ < min(Sep A Δ, ..., Sep D Δ)
- Additive: otherwise

**Formatting**:
- `booktabs` rules
- Caption: "Synergy analysis: Combined vs sum of individual improvements."

---

## Figures

### F1: Error Distribution Stacked Bar (R11, C13, C15)

**Purpose**: Visualize error composition per run. Each bar = one run, segments = D9 error categories. Satisfies R11 ("visualizations illustrating mistake type differences").

**Specification**:
- **X-axis**: 6 bars, one per run (Baseline, +A, +B, +C, +D, Combined)
- **Y-axis**: Error count (absolute) or percentage (0-100%)
- **Segments** (bottom to top, consistent order): No answer, Format only, No reasoning, Arithmetic error, Wrong setup, Gibberish
- **Color palette**: `Set2` (6 colors, colorblind-friendly)
- **Labels**: Percentage value inside each segment if ≥ 5%
- **Legend**: Horizontal, below x-axis
- **Size**: Single-column width (~3.5 inches wide)
- **Output**: `fig_error_distribution.pdf`

**Two variants** (side by side or separate):
- (a) Absolute counts — shows total error volume per run
- (b) Percentages — normalizes to 100%, shows composition shift

### F2: Error Delta Bar Chart (R11, C14, C15)

**Purpose**: Show how each error category's share changes from Baseline to each reward-modified run. Directly visualizes error distribution delta (derived metric).

**Specification**:
- **X-axis**: D9 error categories (6 categories)
- **Y-axis**: Percentage point change vs Baseline (signed: positive = category grew, negative = shrank)
- **Series**: 5 grouped bars per category (one per non-Baseline run), colored by run
- **Zero line**: Horizontal dashed line at y=0
- **Color palette**: 5 distinct colors for runs
- **Significance threshold**: Horizontal dashed lines at ±5 pp (per ablation significance criteria)
- **Size**: Full-width (~7 inches wide) to accommodate grouping
- **Output**: `fig_error_delta.pdf`

### F3: Mean Reward Overlay (C1-C5)

**Purpose**: Compare training dynamics across all 6 runs. Shows whether reward-modified runs learn faster/better/worse than Baseline.

**Specification**:
- **X-axis**: Training step (0, 60, 120, ..., 467)
- **Y-axis**: Mean reward per step
- **Series**: 6 lines, one per run, distinct colors + markers
- **Legend**: Inside plot (upper-left or best-fit)
- **Line style**: Solid for all, markers at checkpoint steps (circle, square, triangle, etc.)
- **Size**: Single-column width (~3.5 inches)
- **Output**: `fig_reward_curves.pdf`

### F4: Per-Component Reward Plot (C11, R13, R19)

**Purpose**: Show which component rewards are active/inactive in the Combined run. Reveals synergy vs interference between reward components.

**Specification**:
- **X-axis**: Training step (0, 60, 120, ..., 467)
- **Y-axis**: Mean reward per component
- **Series**: 5 lines (Original, Format Compliance, Numeric Proximity, C, D) — Combined run only
- **Legend**: Inside plot or to the right
- **Line style**: Solid, distinct colors matching F1/F2 color scheme where possible
- **Size**: Single-column width (~3.5 inches)
- **Output**: `fig_component_rewards.pdf`

**Interpretation guidance** (for writeup):
- Component reward increasing → actively being optimized
- Component reward flat → not engaged by optimizer
- Component reward decreasing → in conflict with other components

### F5: Sequence Length Overlay (C1-C5)

**Purpose**: Detect if reward shaping causes degenerate response lengths. Diagnostic complement to F3.

**Specification**:
- **X-axis**: Training step (0, 60, 120, ..., 467)
- **Y-axis**: Mean sequence length (tokens)
- **Series**: 6 lines, one per run, same colors as F3
- **Horizontal reference**: Dashed line at 256 (max token limit)
- **Legend**: Shared with F3 if placed as subfigure, otherwise independent
- **Size**: Single-column width (~3.5 inches)
- **Output**: `fig_seq_length.pdf`

---

## Global Formatting

**matplotlib rcParams** (applied to all figures):

```python
rcParams = {
    'font.size': 9,
    'font.family': 'serif',
    'lines.linewidth': 1.0,
    'axes.linewidth': 0.5,
    'mathtext.fontset': 'stix',
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'figure.figsize': (3.5, 2.5),  # single-column default
}
```

**Run color mapping** (consistent across F1-F5):

| Run | Color | Marker |
|-----|-------|--------|
| Baseline | Gray (#666666) | ○ |
| + A (Format) | Blue (#1f77b4) | □ |
| + B (Proximity) | Orange (#ff7f0e) | △ |
| + C | Green (#2ca02c) | ▽ |
| + D | Red (#d62728) | ◇ |
| Combined | Purple (#9467bd) | ★ |

**Error category color mapping** (consistent across F1, F2):

| Category | Color (Set2) |
|----------|------|
| No answer | #66c2a5 |
| Format only | #fc8d62 |
| No reasoning | #8da0cb |
| Arithmetic error | #e78ac3 |
| Wrong setup | #a6d854 |
| Gibberish | #ffd92f |

---

## Requirement Coverage

| Requirement | Asset(s) |
|-------------|----------|
| R8 (classify mistakes) | T1 (extraction fail), F1 (error categories) |
| R9 (compare mistake types) | F1 (stacked bar), F2 (delta bar), T2 (gained/lost) |
| R10 (impact commentary) | T2 (gained/lost), T3 (synergy) |
| R11 (visualizations) | F1 (error distribution), F2 (error delta) |
| R12 (summary table) | T1 (summary results) |
| R13 (per-change impact) | T3 (synergy), F4 (per-component rewards) |
| R19 (reward interactions) | F4 (per-component rewards) |

## Metric Coverage

| Metric (from design-metrics.md) | Asset(s) |
|---------------------------------|----------|
| Mean reward | F3 |
| Per-component mean reward | F4 |
| Mean sequence length | F5 |
| Pass@1 | T1, T3 |
| Pass@8 | T1 |
| Pass@8−Pass@1 gap | T1 |
| Extraction failure rate | T1 |
| Per-category error counts | F1 |
| Per-category error percentages | F1, F2 |
| Net problem delta | T2 |
| Error distribution delta | F2 |

Every metric appears in at least one asset. Every run from D3 appears in T1, F1, F3, F5.

## Comparison Coverage

| Comparison (from design-ablation.md) | Asset(s) |
|--------------------------------------|----------|
| C1-C5 (vs Baseline) | T1, T2, F3, F5 |
| C6-C9 (vs Combined) | T1 (all runs in same table) |
| C10 (synergy) | T3 |
| C11 (per-component) | F4 |
| C12 (problem overlap) | T3 (problems gained row) |
| C13 (Baseline vs Combined errors) | F1 |
| C14 (Baseline vs each Separate errors) | F2 |
| C15 (visualization of C13+C14) | F1, F2 |
