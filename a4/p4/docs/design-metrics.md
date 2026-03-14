# Metrics Design

## Selected Observation Points

Two observation points, matching nanochat's natural architecture:

1. **Training-time** — W&B logs, sampled every 60 steps (~8 checkpoints over 467 steps)
2. **Post-training** — full test set evaluation on final checkpoint (1319 GSM8k problems, 8 samples per problem)

No mid-training full eval — training curves from W&B provide sufficient intermediate signal for our short training run.

## Selected Metrics

### Training-Time Metrics (W&B)

| Metric | What it measures | Serves | Justification |
|--------|-----------------|--------|---------------|
| Mean reward | Overall learning signal per step | R5, R7 | Universal RL diagnostic. Confirms training is progressing. Plotted per run for cross-run comparison. |
| Per-component mean reward | Individual reward function contribution | R5, R7, R13 | Prevents combined run from being a black box. Shows which component rewards are being optimized and whether they conflict. Required for R13 (commentary on impact of each change). |
| Mean sequence length | Response length trend under reward pressure | Diagnostic | Detects if reward shaping causes degenerate short/long responses. Our 256-token limit makes length drift operationally relevant. |

**Excluded training-time metrics**:
- *Policy entropy*: Would require adding entropy computation to nanochat's RL loop. Informative for mode collapse detection but not required by any R-number. Overhead not justified.
- *KL divergence*: Not available — nanochat uses pure REINFORCE with no reference model. Would require architectural change.
- *Gradient norms*: Useful for debugging training instability but not needed for comparison across reward configurations.

### Post-Training Metrics (Final Eval)

| Metric | What it measures | Serves | Justification |
|--------|-----------------|--------|---------------|
| Pass@1 (strict) | Headline accuracy — fraction of problems with at least one correct response out of 1 sample | R5, R7, R12 | Universal primary metric. All surveyed papers report this. Goes in summary table (R12). |
| Pass@8 | Knowledge ceiling — fraction of problems solved at least once in 8 samples | R5, R7 | Separates "model knows it" from "model reliably produces it." Gap between Pass@1 and Pass@8 diagnoses whether rewards improve consistency vs capability. Validated by Pass@k literature. |
| Extraction failure rate | Fraction of responses without parseable `#### <number>` answer | R12 | Separates "can't format" from "formatted wrong answer." Cheap to compute. Included in summary table. |
| Per-category error counts | Count of failed problems in each D9 taxonomy category | R8, R9, R11 | Directly answers R8 (classify mistakes) and feeds R9 (compare mistake types). Categories: No answer, Format only, No reasoning, Arithmetic error, Wrong setup, Gibberish. |
| Per-category error percentages | Error counts as fraction of total errors per run | R9, R11 | Normalizes for different total error counts across runs. Required for meaningful cross-run comparison of error distribution shape. |
| Net problem delta (gained/lost) | Which specific problems flip correct↔incorrect between runs | R9, R10 | Decomposes raw accuracy change into improvements and regressions. "Run X gained 20 but lost 8 vs Baseline" is more informative than "Run X is +12." Answers R10 (impact of additional rewards). |

**Excluded post-training metrics**:
- *Relaxed accuracy*: Conflates format errors with math errors (per D10). Dropped.
- *G-Pass@k*: More principled stability metric but adds complexity beyond our comparative scope. Pass@1 + Pass@8 pair is sufficient.
- *Majority voting accuracy*: Aggregation layer that obscures per-run comparison. Not needed.
- *Statistical significance tests*: With ~1100 error problems per run and 6 error categories, distribution shifts are visually clear. Chi-squared test adds formality without insight for our sample sizes.

### Derived Metrics (Analysis-Time)

| Metric | Derived from | Serves | Justification |
|--------|-------------|--------|---------------|
| Pass@8 − Pass@1 gap | Pass@1, Pass@8 | R5, R7, R13 | Quantifies consistency gap. Large gap = model knows more than it produces. Useful for interpreting reward impact. |
| Error distribution delta | Per-category counts (run X vs Baseline) | R9, R10, R11 | Change in each error category between runs. Directly visualizable as delta bar chart (R11). Answers R10. |

## Requirement Coverage Verification

| Requirement | Metric(s) that serve it |
|-------------|------------------------|
| R5 (compare combined to original) | Pass@1, Pass@8, mean reward, per-component reward, net problem delta |
| R7 (compare separate to original + combined) | Pass@1, Pass@8, mean reward, per-component reward, net problem delta |
| R8 (classify mistakes original + combined) | Per-category error counts (D9 taxonomy applied to both) |
| R9 (compare mistake types) | Per-category error percentages, error distribution delta |
| R10 (comment on impact) | Net problem delta, error distribution delta, Pass@8−Pass@1 gap |
| R11 (visualizations of mistake differences) | Error category stacked bar, delta bar chart |
| R12 (summary table) | Pass@1, Pass@8, extraction failure rate, per-category counts — all runs in one table |
| R13 (commentary on each change) | Per-component reward, net problem delta, error distribution delta |
| R19 (reward interactions in combined) | Per-component reward (shows synergy/interference) |

Every requirement has at least one metric. Every metric has at least one requirement justification. No orphan metrics.

## Comparison Matrix

Which comparisons each metric enables:

| Comparison | Required by | Metrics used |
|-----------|-------------|-------------|
| Combined vs Original (Baseline) | R5 | Pass@1, Pass@8, error counts, net delta |
| Separate A vs Original | R7 | Pass@1, Pass@8, error counts, net delta |
| Separate B vs Original | R7 | Pass@1, Pass@8, error counts, net delta |
| Separate C vs Original | R7 | Pass@1, Pass@8, error counts, net delta |
| Separate D vs Original | R7 | Pass@1, Pass@8, error counts, net delta |
| Separate X vs Combined | R7 | Pass@1, Pass@8, per-component reward |
| Combined error distribution vs Original | R8, R9 | Per-category counts + percentages |
| Training dynamics across all | R5, R7 | Mean reward, per-component reward, seq length curves |
