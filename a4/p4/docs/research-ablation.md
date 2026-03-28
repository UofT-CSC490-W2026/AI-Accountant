# Ablation Research

## 1. Formulation

### Motivation

This research defines how to structure experiments so that every required comparison is clearly stated, variables are identified, and we know what constitutes a meaningful result. The ablation design must serve these requirements:

- **R4**: Use same configuration as original RL script (controlled variable)
- **R5**: Compare combined run to original RL run
- **R6**: Run separate: original correctness + each additional reward in its own training run
- **R7**: Compare separate runs to original RL and to combined run
- **R13**: Commentary on the impact of each change

Using these inputs:

**D3 — Run Configuration** (6 runs):

| Run | Rewards Used |
|-----|-------------|
| Baseline | Original only |
| Separate A | Original + Format Compliance |
| Separate B | Original + Numeric Proximity |
| Separate C | Original + C (post-P3) |
| Separate D | Original + D (post-P3) |
| Combined | Original + A + B + C + D |

**Dependent variables** (from design-metrics.md):
- Training-time: mean reward, per-component mean reward, mean sequence length
- Post-training: Pass@1, Pass@8, extraction failure rate, per-category error counts, per-category error percentages, net problem delta
- Derived: Pass@8-Pass@1 gap, error distribution delta

**Constraints**:
- Pure REINFORCE, no KL, binary reward baseline
- 1 epoch, 467 steps, 16 samples/example, 256 max tokens
- Same checkpoint, same hyperparameters across all runs (R4)
- Single run per configuration (no repeated runs for variance estimation)

### Research Questions

**RQ1: How to structure pairwise and ablative comparisons across the D3 run table?**

*Grounding*: D3 defines 6 runs. R5 requires Combined vs Baseline. R6 requires each Separate run. R7 requires Separate vs Baseline AND Separate vs Combined. We need a systematic comparison structure that covers all these requirements without redundancy.

*Sub-questions*:
- What is the standard comparison structure in reward ablation papers? (pairwise, leave-one-out, factorial?)
- How do papers with combined reward runs decompose the combined effect into individual contributions?
- Is there a standard way to present ablation results (comparison tables, ablation matrices)?

**RQ2: What counts as a significant difference in small-scale RL with ~1,300 test problems?**

*Grounding*: R13 requires "commentary on the impact of each change." We need to distinguish signal from noise. With 1319 test problems and ~15-20% accuracy (~200-260 correct), small absolute differences could be noise.

*Sub-questions*:
- What effect sizes do small-scale RL papers report on GSM8k?
- How do papers handle significance when they have a single run per configuration (no confidence intervals from repeated runs)?
- Is per-problem overlap analysis (gained/lost) a more robust signal than aggregate accuracy difference?
- What magnitude of error category shift is considered meaningful?

**RQ3: How to decompose combined-run effects into individual reward contributions?**

*Grounding*: R5 compares Combined to Baseline. R7 compares each Separate to Combined. R13 asks for per-change impact. The Combined run includes all 4 additional rewards — we need to attribute its behavior to individual components.

*Sub-questions*:
- Can per-component reward curves (from W&B) show which rewards are active vs inactive in the combined run?
- Does comparing Combined to each Separate run reveal synergy (Combined > sum of Separate improvements) or interference (Combined < worst Separate)?
- What frameworks exist for attributing combined RL effects to individual reward components?

### Search Strategy

**Sources to consult**:
1. Papers on multi-reward RL training and reward composition
2. Papers on ablation study methodology in NLP/ML
3. GSM8k and math reasoning papers with multiple reward configurations
4. Statistical methodology for single-run comparisons

**Search terms**:
- "ablation study reward function reinforcement learning LLM"
- "multi-reward RL decomposition synergy interference"
- "GSM8k reward comparison significance effect size"
- "single run comparison methodology machine learning"
- "reward composition RLHF ablation"

---

## 2. Results

### RQ1: Comparison structure for reward ablation

**Standard ablation structure**: Leave-One-Component-Out (LOCO) is the most common ablation format in deep learning. Start with a fully functional baseline, remove/alter one component per trial, measure performance with the same metrics. In our case, the "fully functional" system is the Combined run, and each Separate run is effectively "Combined minus 3 rewards."

However, our D3 design is **additive, not subtractive**: Baseline has only the original reward; each Separate run adds one reward; Combined adds all. This means we can frame comparisons in two directions:

**Additive comparisons** (what does adding this reward do?):
- Separate A vs Baseline → effect of adding Format Compliance
- Separate B vs Baseline → effect of adding Numeric Proximity
- Separate C vs Baseline → effect of adding C
- Separate D vs Baseline → effect of adding D
- Combined vs Baseline → effect of adding all (R5)

**Interaction comparisons** (does combining differ from sum of parts?):
- Combined vs each Separate → does the Combined run outperform individual additions? (R7)
- Sum of Separate deltas vs Combined delta → synergy (Combined > sum) or interference (Combined < sum)

**Multi-reward decomposition approaches from literature**:
- **Hierarchical multi-reward** (ACL 2024): Combine holistic + aspect-specific rewards, decompose supervision signal. Our per-component reward logging in W&B directly enables this — we can see which component rewards are active during combined training.
- **Constraint decomposition** (2025): Separate multi-objective instructions into orthogonal components. Relevant because our rewards target different failure modes (format, proximity, P3-derived), so they should be approximately orthogonal.
- **Composite RM overoptimization** (Moskovitz et al., 2023): Correlation between component RMs affects overoptimization points. If our rewards correlate (e.g., format and correctness), the combined run may overoptimize earlier.

**Presentation format**: Standard ablation tables list runs as rows, metrics as columns. Our comparison matrix from design-metrics.md already defines this structure. No novel format needed.

**Sources**:
- [Confronting Reward Model Overoptimization with Constrained RLHF](https://arxiv.org/abs/2310.04373)
- [Information-Theoretic Reward Decomposition](https://arxiv.org/abs/2504.06020)
- [Constraint Decomposition for Multi-Objective Instruction-Following](https://optimization-online.org/2025/12/constraint-decomposition-for-multi-objective-instruction-following-in-large-language-models/)
- [Sotopia-RL: Multi-Dimensional Reward Design](https://arxiv.org/html/2508.03905v1)

### RQ2: Significance criteria for single-run comparisons

**The core problem**: We have single runs per configuration (no repeated runs for variance estimation). With 1319 test problems and ~15-20% accuracy, small differences in Pass@1 could be noise from RL training stochasticity.

**What the literature says**:
- **RLiable** (NeurIPS 2021): Reporting point estimates without confidence intervals hinders reproducibility. In small-run settings, claimed improvements are only 50-70% likely to replicate. They recommend stratified bootstrap CIs and performance profiles.
- **GSM8K-Platinum**: Original GSM8K has label noise that obscures real performance differences. Models with similar accuracy can have very different error profiles (e.g., Claude 3.7 Sonnet vs Llama 405B had identical error counts on original GSM8K but 8x difference on cleaned version).
- **RLVR limits**: Many observed gains reflect sampling efficiency rather than genuine capability expansion. Random rewards can sometimes produce similar gains, especially on contamination-prone benchmarks.

**Practical significance criteria for our setup** (synthesized from literature):

1. **Accuracy threshold**: With 1319 problems, a 1-problem difference = 0.076%. A 1% accuracy difference = ~13 problems. Given RL training variance, differences under ~1% (13 problems) should be treated as noise. Differences of 2%+ (26+ problems) are likely meaningful.

2. **Per-problem overlap is more robust**: Rather than comparing aggregate accuracy, comparing which specific problems flip correct↔incorrect is more informative and less susceptible to aggregate noise. If Separate A gains 30 problems but loses 15 vs Baseline, the net +15 is more reliable than a bare "+1.1%" number because it shows the mechanism.

3. **Error category shifts**: A meaningful shift is when the rank order of error categories changes, or when a category's share changes by >5 percentage points. Small absolute shifts in rare categories (like Gibberish) are noise.

4. **Training curve trends**: Per-component reward trends that consistently increase/decrease over training are more informative than final-checkpoint-only comparisons. If a reward component shows consistent upward trend in training but doesn't improve eval accuracy, that's informative about reward hacking.

5. **Pass@8-Pass@1 gap changes**: If the gap narrows from Baseline to a Separate run, the reward is improving consistency. This is interpretively meaningful regardless of absolute Pass@1 improvement.

**Key insight**: Since we can't do repeated runs, we should emphasize **qualitative comparison patterns** (which problems flip, which error categories shift, which training curves diverge) over **point estimate differences** in aggregate accuracy. Commentary (R13) should acknowledge single-run limitation.

**Sources**:
- [RLiable: Reliable Evaluation in RL](https://research.google/blog/rliable-towards-reliable-evaluation-reporting-in-reinforcement-learning/)
- [GSM8K-Platinum](https://gradientscience.org/gsm8k-platinum/)
- [Limits of RLVR](https://limit-of-rlvr.github.io/)
- [RLVR Makes Models Faster, Not Smarter](https://www.promptfoo.dev/blog/rlvr-explained/)

### RQ3: Decomposing combined-run effects

**Per-component reward curves**: Our design (from design-metrics.md) already includes per-component mean reward logged to W&B. In the Combined run, this shows:
- Which reward components are being actively optimized (reward increasing)
- Which are stagnant or decreasing (potentially ignored by the optimizer or in conflict)
- Whether components co-increase (synergy) or trade off (interference)

**Synergy vs interference detection**: From the multi-reward literature:

| Pattern | What it means | How to detect |
|---------|--------------|---------------|
| **Synergy** | Combined > sum of individual improvements | Combined Pass@1 delta > (Sep A delta + Sep B delta + Sep C delta + Sep D delta) |
| **Interference** | Combined < best individual | Combined Pass@1 < max(Sep A, Sep B, Sep C, Sep D) |
| **Additivity** | Combined ≈ sum of individual improvements | Combined delta ≈ sum of Separate deltas |
| **Redundancy** | Some rewards have no marginal effect | Removing a reward from Combined doesn't change performance |

Since we don't have "Combined minus one" runs, we can't do full leave-one-out analysis. But we can approximate:
- Compare Combined to each Separate → if Combined ≈ Separate A, then B/C/D may not be contributing
- Per-component reward curves in Combined → if component B's reward is flat while A's increases, B may be inactive
- Per-problem delta analysis → overlap between problems gained by Separate A and problems gained by Combined reveals whether Combined is "riding" on A's improvements

**Attribution is approximate, not causal**: With single runs and no factorial design, we can describe observed patterns but cannot make causal claims about individual reward contributions in the combined run. Commentary (R13) should present this as "observed patterns consistent with" rather than "caused by."

**Sources**:
- [Confronting Reward Model Overoptimization](https://arxiv.org/abs/2310.04373) — composite RM correlation effects
- [Hierarchical Multi-Reward RLHF](https://aclanthology.org/2024.findings-acl.465.pdf) — decomposition approach
- [Sotopia-RL](https://arxiv.org/html/2508.03905v1) — multi-dimensional reward ablation confirming component necessity
