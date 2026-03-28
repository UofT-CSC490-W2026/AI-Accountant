# Metrics Research

## 1. Formulation

### Motivation

This research defines what to measure and where, so that the experimental results can answer every comparison required by the assignment. The measurement design must serve these requirements:

- **R5**: Compare combined run (all additional rewards) to original RL run
- **R7**: Compare each separate run (original + one additional reward) to both original RL and combined run
- **R8-R9**: Classify mistakes from original RL and combined RL, compare mistake types between them
- **R11**: Create visualizations illustrating mistake type differences
- **R12**: Summary table of all results

And operate within these constraints (from item 1 findings):

- **Algorithm**: Pure REINFORCE, no KL regularization, no PPO ratio/clip
- **Reward**: Binary correctness (1.0 if answer matches gold, 0.0 otherwise), returned as float
- **Advantage**: `rewards - rewards.mean()` (no z-score normalization)
- **Training**: 1 epoch, 16 examples/step, 16 samples/example, 467 steps, max 256 tokens
- **Eval/save**: Every 60 steps during training
- **Test set**: 1319 GSM8k test problems
- **Starting accuracy**: 15.39% strict GSM8k (P2 SFT checkpoint)

### Research Questions

**RQ1: What metrics do RL-for-math papers use to compare reward configurations?**

*Grounding*: R5 and R7 require comparing runs. We need to know what the field considers standard comparison metrics for math RL beyond raw accuracy. This determines what goes in the summary table (R12).

*Sub-questions*:
- What accuracy variants exist (strict match, relaxed match, parseable rate)?
- Do papers report per-problem gain/loss deltas or only aggregate scores?
- What training-time diagnostics are standard (reward curves, gradient norms, entropy)?

**RQ2: What observation points exist — training-time diagnostics vs post-training evaluation?**

*Grounding*: Item 1 shows nanochat has two natural observation points: (a) per-step metrics during training (logged every 60 steps to W&B), and (b) post-training evaluation on the full test set. We need to decide what to measure at each.

*Sub-questions*:
- What training-time signals are informative for detecting reward impact (mean reward, per-component reward, loss, sequence length)?
- What post-training evaluation metrics go beyond accuracy (error categorization, consistency across samples)?
- Is there value in mid-training evaluation checkpoints, or is final-only sufficient?

**RQ3: What metrics separate "model learned the skill" from "model is consistent"?**

*Grounding*: D10 already proposes Pass@1 (headline accuracy) and Pass@8 (knowledge vs consistency). We need to validate this choice and understand whether other approaches exist. A model that gets 30% Pass@1 but 50% Pass@8 knows more than it reliably produces — this distinction matters for interpreting reward impact.

*Sub-questions*:
- How is Pass@k used in math reasoning evaluation? What values of k are standard?
- Are there alternatives to Pass@k for measuring consistency (majority voting, self-consistency)?
- What does the gap between Pass@1 and Pass@k tell us about the model?

**RQ4: What metrics capture error distribution shifts across runs?**

*Grounding*: R8-R9 require classifying and comparing mistakes. R11 requires visualizing mistake differences. D9 defines a rule-based taxonomy. We need metrics that quantify how the mistake distribution changes when rewards change.

*Sub-questions*:
- How do papers measure shifts in error type distributions?
- What visualization approaches show error category changes across experimental conditions?
- Is per-problem tracking (which specific problems flip between correct/incorrect) standard?

### Search Strategy

**Sources to consult**:
1. Papers on RLHF/RLVR for math reasoning (GSM8k, MATH, competition math)
2. Papers on reward shaping for language models
3. Nanochat/Karpathy baseline documentation and existing eval code
4. Standard RL evaluation methodology papers

**Search terms**:
- "GSM8k reward function evaluation metrics"
- "RLHF math reasoning comparison metrics"
- "Pass@k math evaluation"
- "error analysis reward shaping language model"
- "REINFORCE reward comparison ablation study metrics"
- "mistake classification distribution shift NLP"

---

## 2. Results

### RQ1: Metrics for comparing reward configurations

**Accuracy variants**:
- **Strict match (Pass@1)**: The universal primary metric. All surveyed papers (DeepSeekMath, Reward-Robust RLHF, The Good/Bad/Hybrid) report Pass@1 as the headline comparison metric. For GSM8k, this means extracting a numeric answer via regex and comparing to gold.
- **Parseable rate / extraction failure rate**: Not always reported explicitly, but implicit in strict match — if the model doesn't produce a parseable answer, it scores 0. Worth tracking separately to distinguish "can't format" from "formatted wrong answer."
- **Relaxed match**: Some papers use more lenient parsing. D10 already decided to drop relaxed accuracy as it conflates format and math correctness. Confirmed as reasonable — no surveyed paper argues relaxed match is essential.

**Per-problem tracking**:
- DeepSeekMath and GRPO literature track aggregate scores, not per-problem deltas. However, per-problem tracking (which specific problems flip correct↔incorrect between runs) is standard in ablation studies and error analysis papers. It's how you compute "net problem delta" — problems gained minus problems lost vs baseline.
- This is essential for R8-R9 (comparing mistakes) and not over-engineering — it's how you populate the error category breakdown.

**Training-time diagnostics** (standard in RL-for-LLM papers):
- **Mean reward per step**: Most direct signal of learning progress. All RLHF papers plot this.
- **Per-component reward**: When using multiple reward signals, logging each component separately prevents the combined run from being a black box. DeepSeek uses accuracy + format rewards logged separately.
- **Policy entropy**: Higher entropy = more exploration. Useful to detect mode collapse. Not always logged but recommended in RL diagnostics literature.
- **KL divergence from reference**: Standard in PPO/RLHF. However, nanochat uses pure REINFORCE with no KL penalty, so this is not available without adding it. Not applicable to our setup.
- **Sequence length**: Tracks whether the model learns to produce longer/shorter outputs. Relevant because our 256 max token limit is tight.

**Sources**:
- [Does RLHF Scale?](https://arxiv.org/html/2412.06000v1) — systematic analysis of scaling properties in RLHF
- [The Good, The Bad, and The Hybrid](https://arxiv.org/html/2511.13016) — reward structure comparison on GSM8k
- [Reward-Robust RLHF](https://arxiv.org/html/2409.15360v1) — robust reward strategies for GSM8k
- [DeepSeekMath](https://arxiv.org/abs/2402.03300) — GRPO with rule-based accuracy + format rewards

### RQ2: Observation points (training-time vs post-training)

**Training-time observation point** (W&B, logged every 60 steps):
- Mean reward and per-component reward — primary training signal
- Pass@1 on eval subset — nanochat evaluates on 400 problems periodically during training
- Mean sequence length — detects response length drift under reward pressure
- These are already available in nanochat's RL loop. Per-component reward requires a small code change to log each reward function's output separately.

**Post-training observation point** (full test set eval, 1319 problems):
- Pass@1 — headline accuracy, one response per problem
- Pass@8 — generate 8 responses per problem, measures knowledge vs consistency (see RQ3)
- Extraction failure rate — fraction of responses that don't match `#### <number>` pattern
- Per-problem features — for each problem: correct/incorrect, parseable, extracted answer, gold answer, full response text. These feed into error categorization.

**Mid-training checkpoints**:
- Nanochat saves every 60 steps. Running full eval at intermediate checkpoints is expensive and adds limited value for our comparison goals. Reward-Robust RLHF notes that reward may continue growing while capability degrades — but our training is short (467 steps, ~8 checkpoints), so training curves from W&B are sufficient.
- **Decision**: Final checkpoint eval only. Training curves provide intermediate signal.

**Sources**:
- [How to Evaluate Reward Models for RLHF](https://arxiv.org/html/2410.14872v1)
- [Unsloth RL Guide](https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide) — practical GRPO training diagnostics
- [Tips for LLM Pretraining and Evaluating RMs](https://magazine.sebastianraschka.com/p/tips-for-llm-pretraining-and-evaluating-rms)

### RQ3: Separating knowledge from consistency (Pass@k)

**Pass@k in math evaluation**:
- Pass@k measures the probability that at least one of k independent samples is correct. It originated in program synthesis (HumanEval) and is now standard in math reasoning evaluation.
- Common values: Pass@1 (headline), Pass@8, Pass@16, Pass@64, Pass@100. DeepSeek-R1-Zero uses pass@1 with 64 samples for GRPO advantage calculation.
- For our setup with 8 samples per problem (D10 specification), Pass@1 and Pass@8 are the natural pair.

**What the gap tells us**:
- If Pass@8 >> Pass@1: the model "knows" the solution for many problems but inconsistently produces it. Additional rewards could help by shaping the output distribution.
- If Pass@8 ≈ Pass@1: the model's failures are genuine — it doesn't know how to solve those problems regardless of sampling. Reward changes would need to teach new capabilities, not just consistency.
- This gap directly interprets whether rewards are improving reliability vs. capability.

**G-Pass@k (ACL 2025)**: A stability-aware variant that quantifies both peak performance and stability across sampling attempts. More principled than raw Pass@k but adds complexity. For our scope (6 runs, comparative focus), standard Pass@1 and Pass@8 are sufficient.

**Self-consistency / majority voting**: Generate k responses, take majority vote as final answer. Equivalent to a filtered Pass@1. Useful in deployment but adds a layer of aggregation that obscures per-run comparison. Not needed for our measurement goals.

**Decision**: Pass@1 (headline) + Pass@8 (knowledge ceiling) is validated. The gap between them is interpretively useful. G-Pass@k and majority voting are not needed.

**Sources**:
- [Pass@k and Unbiased Estimator](https://leehanchung.github.io/blogs/2025/09/08/pass-at-k/)
- [Are Your LLMs Capable of Stable Reasoning? (G-Pass@k)](https://aclanthology.org/2025.findings-acl.905.pdf)
- [Pass@k as Diagnostic, Not Objective](https://arxiv.org/html/2511.16231v1)
- [Don't Pass@k: A Bayesian Framework](https://openreview.net/forum?id=PTXi3Ef4sT)

### RQ4: Measuring error distribution shifts

**Error categorization approaches**:
- GSM8k literature identifies three primary error types: Semantic Misunderstanding (SM), Calculation Error (CE), Step-missing Error (SE). The LEMMA framework adds question misinterpretation and extends with model-specific error harvesting.
- Our D9 rule-based taxonomy (No answer, Format only, No reasoning, Arithmetic error, Wrong setup, Gibberish) is mechanically extractable and covers observable failure modes. It maps reasonably to the literature categories: No answer/Format only ≈ extraction failures, Arithmetic error ≈ CE, Wrong setup ≈ SM, No reasoning ≈ SE.

**Quantifying distribution shifts**:
- **Per-category counts and percentages**: The simplest approach — count errors in each category per run, compare across runs. This is what R8-R9 require.
- **Per-problem tracking**: Track which specific problems each run gets right/wrong. Compute "gained" (wrong→right) and "lost" (right→wrong) problem sets between runs. This decomposes raw accuracy change into gains and regressions.
- **Statistical tests**: Chi-squared test on error category distributions across runs could test whether the distribution shift is statistically significant. However, with only 1319 test problems and ~15% accuracy, the error set is large enough (~1100 problems) that even small category shifts should be visible without formal testing.

**Visualization approaches**:
- **Stacked bar charts**: Error category breakdown per run, side by side. Standard in NLP error analysis (Errudite-style). Directly serves R11.
- **Alluvial/Sankey diagrams**: Show per-problem flow between categories across runs (e.g., "No answer" in run A → "Correct" in run B). Visually compelling but complex; reserve for key comparisons.
- **Heatmaps**: Runs × error categories, cell = count or percentage. Good for the summary table (R12).
- **Delta bar charts**: Show change in each error category (combined vs baseline). Directly answers R9 (impact of additional rewards on mistake types).

**Per-problem tracking is standard**: The LEMMA framework and DUP papers both track per-problem correctness across conditions. This is necessary for computing net problem deltas and error flow diagrams.

**Sources**:
- [LEMMA: Learning from Errors](https://arxiv.org/html/2503.17439v1)
- [Achieving >97% on GSM8K (DUP)](https://arxiv.org/html/2404.14963v3)
- [MR-GSM8K: Meta-Reasoning Benchmark](https://arxiv.org/html/2312.17080v4)
- [Errudite: Scalable Error Analysis](https://medium.com/@uwdata/errudite-55d5fbf3232e)

### Candidate Metrics Summary

| Metric | Observation Point | Purpose | Serves | Pros | Cons |
|--------|------------------|---------|--------|------|------|
| Mean reward | Training (W&B) | Learning signal | R5, R7 | Direct, always available | May not correlate with eval accuracy |
| Per-component reward | Training (W&B) | Decompose combined | R5, R7, R19 | Prevents black-box combined run | Requires code change |
| Sequence length | Training (W&B) | Detect length drift | Diagnostic | Cheap | Indirect |
| Pass@1 | Post-training (1319) | Headline accuracy | R5, R7, R12 | Universal, comparable | Doesn't show knowledge ceiling |
| Pass@8 | Post-training (1319) | Knowledge vs consistency | R5, R7 | Separates capability from reliability | 8x eval cost |
| Extraction failure rate | Post-training (1319) | Format quality | R12 | Cheap, diagnostic | Narrow |
| Per-category error counts | Post-training (1319) | Error distribution | R8, R9, R11 | Directly answers R8-R9 | Depends on taxonomy quality |
| Per-problem delta (gained/lost) | Post-training (1319) | Decompose accuracy change | R9, R10 | Shows regressions | Requires problem-level tracking |
| Error category stacked bar | Visualization | Show distribution | R11 | Clear, standard | Static |
| Delta bar chart | Visualization | Show category changes | R9, R11 | Directly shows impact | Needs baseline reference |
| Summary heatmap/table | Visualization | All runs × all metrics | R12 | Complete overview | Can be dense |
