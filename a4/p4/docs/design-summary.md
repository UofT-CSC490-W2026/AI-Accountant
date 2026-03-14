# Design Summary

## Metrics

### Where to Measure

| Observation Point | Why | Source |
|-------------------|-----|--------|
| **Training-time** (~8 checkpoints, every 60 steps) | See learning dynamics — is reward being optimized? Do components conflict? | W&B logs |
| **Post-training** (final checkpoint, 1319 problems × 8 samples) | Measure actual performance — does the reward improve accuracy and error profile? | Eval script output |

Training-time shows the trajectory. Post-training shows the outcome. Both are needed: a reward that improves training curves but degrades eval accuracy is reward-hacking; a reward that improves eval but shows flat training curves is suspicious.

### What to Measure

| Metric | What it is | Why this metric |
|--------|-----------|-----------------|
| **Mean reward** (training) | Average reward per step | Confirms training progresses. If reward is flat, nothing is being learned. |
| **Per-component mean reward** (training) | Each reward function's average separately | Combined run sums 5 rewards. Without decomposition, we can't attribute behavior to individual components or detect conflicts (R13). |
| **Mean sequence length** (training) | Average response length per step | Detects degenerate behavior — reward accidentally driving responses to minimum or maximum length. |
| **Pass@1** (eval) | Fraction correct with 1 sample | Headline accuracy. Universal comparison metric. Required for R12 summary table. |
| **Pass@8** (eval) | Fraction correct in at least 1 of 8 samples | Knowledge ceiling. Gap with Pass@1 diagnoses consistency vs capability: gap narrows → more reliable, gap widens → broader but less reliable. |
| **Extraction failure rate** (eval) | Fraction without parseable `#### <number>` | Separates format failure from reasoning failure. Directly measures Reward A's target behavior. |
| **Per-category error counts** (eval) | Failed problems per D9 category | Tells us *why* accuracy changed, not just that it did (R8). Categories: No answer, Format only, No reasoning, Arithmetic error, Wrong setup, Gibberish. |
| **Per-category error %** (eval) | Counts normalized by total errors | Makes composition comparable across runs with different total error counts. |
| **Net problem delta** (eval) | Problems gained and lost vs Baseline | More robust than aggregate %. "Gained 30, lost 5" reveals mechanism; "+1.9%" hides it. |
| **Pass@8−Pass@1 gap** (derived) | Difference between knowledge ceiling and headline accuracy | Diagnoses what a reward does to consistency. |
| **Error distribution delta** (derived) | Change in each category's share vs Baseline | Directly answers "which error types did this reward fix or worsen?" |

---

## Assets

### What Must Be Shown and How

| What must be shown | Asset | Why this asset type |
|--------------------|-------|---------------------|
| All runs × headline metrics in one place (R12) | **T1: Summary table** (LaTeX tabular) | Standard format — rows=runs, cols=metrics, bold best. Reader gets the full picture in one glance. |
| Per-problem correctness changes vs Baseline (R9, R10) | **T2: Gained/lost table** (LaTeX tabular) | Table is clearest for gained/lost counts. Exposes churn that aggregate accuracy hides. |
| Whether rewards interact as synergy or interference (R13) | **T3: Synergy table** (LaTeX tabular) | Compact comparison: Combined Δ vs sum of Separate Δs. Table is sufficient — only 2 rows. |
| Error type composition across runs (R11) | **F1: Stacked bar chart** (matplotlib → PDF) | Part-to-whole visualization. Each bar = one run, segments = error categories. Shows both total errors and composition at once. ≤6 segments keeps it readable. |
| Direction and magnitude of error shifts (R11) | **F2: Delta bar chart** (matplotlib → PDF) | Grouped bars showing pp change per category. Directly shows "what changed" — stacked bar shows composition, delta bar shows movement. They complement each other. |
| Training dynamics across runs | **F3: Mean reward overlay** (matplotlib → PDF) | 6 lines on one plot. Overlay is standard for comparing same metric across conditions (Berkeley CS294 convention). Small multiples would waste space for only 6 lines. |
| Which reward components are active in Combined run (R19) | **F4: Per-component reward plot** (matplotlib → PDF) | 5 lines (one per component) for Combined run only. Reveals active/inactive/conflicting components — no other asset type can show this. |
| Degenerate response length behavior | **F5: Sequence length overlay** (matplotlib → PDF) | Same format as F3. Diagnostic — catches pathological length drift. |

All figures output as PDF vectors (infinitely zoomable, standard for NLP venues). All tables as LaTeX tabular with `booktabs` (standard, not images).

---

## Rewards A and B

### What We Chose

| Reward | Formula | Target |
|--------|---------|--------|
| **A: Format Compliance** | 1.0 if `#### <number>` regex matches, 0.0 otherwise | Independent format signal |
| **B: Numeric Proximity** | `max(0, 1 − |pred − gold| / (|gold| + 1))` if parseable, 0.0 otherwise | Partial credit for close answers |

### Justification from Karpathy's RL Results

Karpathy's nanochat uses binary correctness reward only (1.0 exact match, 0.0 otherwise). Results across configurations:

| Config | SFT → RL | Lift |
|--------|----------|------|
| Speedrun (~560M) | 4.55% → 7.58% | +3.0pp |
| $1000 tier (d32) | 12.74% → 19.94% | +7.2pp |
| d34 (~$2,500) | 12.96% → 23.05% | +10.1pp |

Our model is depth 20 with SwiGLU (`a4p2-sft-metamath-swiglu`, `n_layer=20`, `n_embd=1280`), starting at 15.39% strict accuracy. Comparable to Karpathy's $1000 tier in scale.

**Pattern observed**: Binary reward roughly doubles accuracy but has two structural weaknesses that persist across all model sizes and training durations:

1. **Format and correctness are conflated.** A response with `#### 42` (wrong answer) gets the same 0.0 as a response with no `####` at all. The model can only learn formatting as a byproduct of getting correct answers — there is no independent format signal. Our SFT checkpoint has 11% format failure; binary reward provides no direct pressure to fix this.

2. **Zero gradient on hard problems.** With 16 samples per example, if 0/16 are correct, all advantages are 0 and no gradient flows. Binary reward treats a response computing 98 (when gold is 100) identically to gibberish. The persistent pass@8 >> pass@1 gap in Karpathy's results confirms the model has latent capability it cannot reliably produce, yet binary reward gives no signal to improve reliability.

**Reward A** addresses weakness 1: gives explicit credit for `#### <number>` format independent of correctness. **Reward B** addresses weakness 2: gives graded signal on every parseable response, breaking the sparse gradient barrier.

These are structural properties of binary reward, not artifacts of model architecture or training duration. SwiGLU vs standard MLP does not change the reward landscape — the weaknesses apply equally to any model trained with binary correctness reward on GSM8K.

### Literature Grounding

**Reward A (Format Compliance)**:
- GSM8K-RLVR (Mohammadjafari80): tiered scoring with 0.1 for format compliance
- veRL framework GSM8K example: 0.1 for formatted-but-incorrect
- Unsloth RL documentation: format adherence as standard component
- Tulu3-inspired RLVR implementations: consistent format signal
- We use 1.0 instead of 0.1 because our advantage computation is `rewards − mean` (not z-score); at 0.1 the format signal is negligible

**Reward B (Numeric Proximity)**:
- Unsloth RL documentation: explicitly describes proximity-based reward for math
- Ng et al. (1999): reward shaping preserves optimal policy while accelerating learning
- Andrychowicz et al. (2017): sparse rewards are a fundamental RL challenge; partial credit is the classic solution
