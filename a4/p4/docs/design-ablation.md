# Ablation Design

## Experimental Variables

### Controlled Variables (held constant across all runs per R4)

| Variable | Value | Source |
|----------|-------|--------|
| Starting checkpoint | `a4p2-sft-metamath-swiglu` step 24633 | D1 |
| Algorithm | Pure REINFORCE, no KL, no PPO | Item 1 |
| Epochs | 1 | Item 1 |
| Training steps | 467 | Item 1 |
| Examples per step | 16 | Item 1 |
| Samples per example | 16 | Item 1 |
| Max tokens | 256 | Item 1 |
| Temperature | 1.0 | Item 1 |
| Top-k | 50 | Item 1 |
| Learning rates | matrix 0.02, embed 0.2, unembed 0.004 | Item 1 |
| Eval/save frequency | Every 60 steps | Item 1 |
| Test set | 1319 GSM8k problems | Item 1 |
| Eval samples per problem | 8 | D10 |

### Independent Variable

The **reward configuration** is the only variable that differs across runs:

| Run | Original | A (Format) | B (Proximity) | C (post-P3) | D (post-P3) |
|-----|----------|-----------|---------------|-------------|-------------|
| Baseline | Yes | — | — | — | — |
| Separate A | Yes | Yes | — | — | — |
| Separate B | Yes | — | Yes | — | — |
| Separate C | Yes | — | — | Yes | — |
| Separate D | Yes | — | — | — | Yes |
| Combined | Yes | Yes | Yes | Yes | Yes |

### Dependent Variables (from design-metrics.md)

**Training-time** (W&B): Mean reward, per-component mean reward, mean sequence length

**Post-training** (final eval): Pass@1, Pass@8, extraction failure rate, per-category error counts (D9), per-category error percentages, net problem delta (gained/lost vs Baseline)

**Derived**: Pass@8−Pass@1 gap, error distribution delta

## Comparisons

### Tier 1: Required Comparisons (directly from assignment)

| ID | Comparison | Requirement | What it answers |
|----|-----------|-------------|-----------------|
| C1 | Combined vs Baseline | R5 | Does adding all rewards together improve over original RL? |
| C2 | Separate A vs Baseline | R6, R7 | Does Format Compliance alone improve over original? |
| C3 | Separate B vs Baseline | R6, R7 | Does Numeric Proximity alone improve over original? |
| C4 | Separate C vs Baseline | R6, R7 | Does C alone improve over original? |
| C5 | Separate D vs Baseline | R6, R7 | Does D alone improve over original? |
| C6 | Separate A vs Combined | R7 | How does A alone compare to all rewards combined? |
| C7 | Separate B vs Combined | R7 | How does B alone compare to all rewards combined? |
| C8 | Separate C vs Combined | R7 | How does C alone compare to all rewards combined? |
| C9 | Separate D vs Combined | R7 | How does D alone compare to all rewards combined? |

### Tier 2: Derived Comparisons (for R13 commentary)

| ID | Comparison | Requirement | What it answers |
|----|-----------|-------------|-----------------|
| C10 | Combined delta vs sum of Separate deltas | R13 | Synergy (Combined > sum) or interference (Combined < sum)? |
| C11 | Per-component rewards in Combined training | R13, R19 | Which components are active/inactive? Do they conflict? |
| C12 | Problem overlap: Separate X gained ∩ Combined gained | R13 | Is Combined's improvement driven by the same problems as each Separate? |

### Tier 3: Error Analysis Comparisons (for R8-R11)

| ID | Comparison | Requirement | What it answers |
|----|-----------|-------------|-----------------|
| C13 | Baseline error distribution vs Combined error distribution | R8, R9 | How do mistake types change when all rewards are added? |
| C14 | Baseline error distribution vs each Separate error distribution | R9 | Which reward targets which error type? |
| C15 | Visualization of C13 and C14 | R11 | Visual evidence of mistake distribution shifts |

## Metrics per Comparison

| Comparison | Pass@1 | Pass@8 | Gap | Extraction | Error counts | Error % | Net delta | Training curves |
|-----------|--------|--------|-----|------------|-------------|---------|-----------|----------------|
| C1-C5 (vs Baseline) | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| C6-C9 (vs Combined) | Yes | Yes | Yes | — | — | — | Yes | — |
| C10 (synergy) | Yes | — | — | — | — | — | — | — |
| C11 (component) | — | — | — | — | — | — | — | Yes (per-component) |
| C12 (overlap) | — | — | — | — | — | — | Yes (set intersection) | — |
| C13-C14 (errors) | — | — | — | — | Yes | Yes | — | — |
| C15 (viz) | — | — | — | — | Stacked bar | Delta bar | — | — |

## Significance Criteria

Since we have single runs per configuration, we cannot compute confidence intervals from repeated runs. Instead, we use the following practical criteria:

### Accuracy (Pass@1, Pass@8)
- **< 1% difference** (~13 problems): Treat as noise. Report but do not claim improvement.
- **1-2% difference** (13-26 problems): Marginal. Report with caveat about single-run limitation.
- **> 2% difference** (26+ problems): Likely meaningful. Report as observed improvement/degradation.

### Per-Problem Delta
- More robust than aggregate accuracy. Always report gained and lost counts separately (not just net).
- A run that gains 30 and loses 5 is a clearer signal than one that gains 15 and loses 2, even if net is similar.

### Error Category Shifts
- **> 5 percentage point change** in a category's share: meaningful shift.
- **Rank order change** among top-3 error categories: meaningful structural shift.
- Small absolute changes in rare categories (< 5% share): noise.

### Training Curves
- **Consistent directional trend** over multiple checkpoints: informative signal.
- **Single-checkpoint spike/dip**: noise.
- **Per-component reward divergence** in Combined: informative about reward interaction.

### Pass@8−Pass@1 Gap
- **Gap narrows**: reward is improving consistency (same knowledge, more reliable output).
- **Gap widens**: reward is expanding knowledge frontier without improving reliability.
- **Gap unchanged**: reward has no differential effect on consistency.

### Caveat for All Comparisons
All commentary (R13) must acknowledge the single-run limitation. Use language like "the observed pattern suggests" rather than "reward X causes." Do not claim statistical significance.

## Requirement Coverage

| Requirement | Comparison(s) |
|-------------|--------------|
| R4 (same configuration) | Controlled variables table — all non-reward parameters identical |
| R5 (combined vs original) | C1, C13 |
| R6 (separate runs) | C2, C3, C4, C5 |
| R7 (separate vs original + combined) | C2-C5 (vs Baseline), C6-C9 (vs Combined) |
| R8 (classify mistakes) | C13, C14 — D9 taxonomy applied to Baseline + Combined |
| R9 (compare mistake types) | C13, C14 — error distribution deltas |
| R10 (impact commentary) | C10, C12 — synergy/overlap analysis |
| R11 (visualizations) | C15 — stacked bar + delta bar charts |
| R12 (summary table) | All Tier 1 comparisons in one table |
| R13 (per-change impact) | C10, C11, C12 — decomposition + component analysis |
| R19 (reward interactions) | C11 — per-component reward curves in Combined |

Every run from D3 appears in at least one comparison. Every comparison maps to at least one requirement.
