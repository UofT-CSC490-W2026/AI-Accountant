# Research: Rewards A/B

## 1. Formulation

### Requirements Driving This Research

- **R1**: Design at least 2 additional reward functions beyond binary correctness
- **R14**: Each reward must have literature justification
- **R2**: Motivate rewards from P3 error analysis patterns — A/B are pre-P3 guesses from literature and baseline inspection; C/D will satisfy R2 fully after P3 delivers

### System Constraints

These constrain what reward designs are feasible:

| Constraint | Value | Implication |
|-----------|-------|-------------|
| RL algorithm | REINFORCE (no KL, no PPO ratio+clip) | No reference model available; rewards must be self-contained |
| Advantage computation | `rewards - rewards.mean()` (no z-score) | Reward scale matters — large-magnitude rewards will dominate advantage signal |
| Reward interface | `GSM8K.reward(conversation, assistant_response) -> float` | Reward receives the full conversation (with gold answer) and the model's text response; returns a single float |
| Reward call site | `chat_rl.py:131` — called per sample after decoding | Reward sees final decoded text, not intermediate tokens |
| Samples per example | 16 | Mean subtraction across 16 samples; at least some must differ in reward for non-zero gradients |
| Max generation tokens | 256 | Model has limited space for reasoning; reward shouldn't require very long outputs |
| Composition | Additional rewards must compose with binary correctness | Combined run uses Original + A + B + C + D; rewards are summed before advantage computation |
| Training set | GSM8K train (7,473 problems), 1 epoch, 467 steps | Relatively short training horizon — reward signal must be learnable quickly |
| Gold answer format | `#### <number>` extracted via regex | Model must learn this format to get any correctness reward |
| Calculator tool use | `<<expr=result>>` tags in gold solutions | Model can use calculator; engine masks tool tokens from loss |

### Research Questions

**RQ1: What reward functions beyond binary correctness have been used for math reasoning RL?**
- Scope: GSM8K specifically, and grade-school math reasoning more broadly
- What we need: concrete reward formulations (not just categories), with reported effects
- Relevance: directly answers R1 (what to design) and R14 (literature backing)

**RQ2: What are the known weaknesses of binary correctness reward in REINFORCE for math?**
- Scope: sparse reward problems, reward hacking, format vs reasoning, exploration collapse
- What we need: specific failure modes that additional rewards could address
- Relevance: justifies why additional rewards are needed and what they should target

**RQ3: What format/process/outcome reward categories exist, and which are feasible given our constraints?**
- Format rewards: reward structural properties of the response (presence of `####`, step markers, calculator use)
- Process rewards: reward intermediate reasoning steps (requires a verifier model or heuristic)
- Outcome rewards: reward properties of the final answer beyond binary match (partial credit, proximity)
- Feasibility filter: must work with our interface (text in, float out), no external model, composable with binary reward
- Relevance: narrows the design space to implementable candidates

**RQ4: Which reward approaches are most likely to produce observable effects in our short training horizon (467 steps)?**
- Some rewards may be theoretically sound but require thousands of steps to show effects
- We need rewards that give gradient signal from step 1 (not just once the model is already good)
- Relevance: practical constraint — if a reward doesn't move metrics in 467 steps, it's useless for our experiment

### Search Strategy

**Search terms**:
- `GSM8K reward function RL`
- `math reasoning reward shaping REINFORCE`
- `process reward model GSM8K`
- `format reward RL language model`
- `GRPO reward design`
- `sparse reward reinforcement learning language model`
- `reward shaping grade school math`

**Sources to consult**:
1. DeepSeek-Math (Shao et al., 2024) — GRPO with outcome rewards on math
2. Math-Shepherd (Wang et al., 2024) — process reward models for math
3. Let's Verify Step by Step (Lightman et al., 2023) — process vs outcome reward
4. DAPO (Yu et al., 2025) — reward normalization and advantage computation
5. Karpathy's nanochat discussions/1 — the original RL implementation and known behaviors
6. Wei et al. (2022) Chain-of-Thought — GSM8K error taxonomy (semantic misunderstanding, calculation error, step-missing)
7. Any papers citing GSM8K + reward shaping or auxiliary rewards

**Baseline behavior to inspect** (from `gsm8k.py` and `chat_rl.py`):
- What fraction of 16 samples per example get reward 1.0 vs 0.0? (determines advantage variance)
- How often does the model produce parseable `#### <number>` format but with wrong answer?
- How often does the model fail to produce `####` at all? (format failure vs reasoning failure)
- Does the model use calculator `<< >>` tags? How often?
- What is typical sequence length? (is 256 often hit = truncation?)

These questions will be answered during research execution (step 1.11) by inspecting Karpathy's reported baseline behavior and our P2 eval results.

## 2. Results

### Baseline Behavior Analysis

**Source**: P2 eval results (`final_sft_metamath_eval.json`) — our SFT checkpoint before RL, 1319 GSM8K test problems, greedy decoding.

| Metric | Value | Implication |
|--------|-------|-------------|
| Strict accuracy (has `#### <number>`, matches gold) | 15.39% | Very sparse reward — ~85% of samples get 0.0 |
| Parseable rate (has `#### <number>` at all) | 88.93% | ~11% format failure — model doesn't even attempt the answer format |
| Relaxed numeric match (any number matches gold) | 16.22% | Small gap (0.83pp) = few cases where model knows the answer but fails format |

**Observed failure patterns** from sample inspection (64 examples):
- **Format failure** (~11%): Model produces reasoning text but never outputs `#### <number>`. Examples: idx 4, 5, 9, 16, 17 have `strict_pred_num: null`. The model reaches the end without committing to an answer format.
- **Wrong answer with format** (~74%): Model outputs `#### <number>` but the number is wrong. This is the dominant failure mode. Examples: idx 0, 1, 2, 3, 6, 8.
- **Calculator usage is inconsistent**: Some samples use `<|python_start|>` tags for arithmetic (idx 7, 10, 12), others do all computation in natural language and make errors.
- **Reasoning quality varies**: Some responses show structured step-by-step reasoning (idx 11, 15, 21), others ramble, repeat, or set up the problem incorrectly (idx 0, 5, 20).

**Key insight for reward design**: At 15% accuracy, binary reward is extremely sparse. With 16 samples per example, many examples will have 0/16 correct (all advantage = 0, no gradient). A denser reward signal would give non-zero gradients on more examples.

### Literature Findings

#### RQ1: Reward functions for math reasoning RL

**Finding 1: Format compliance reward (tiered scoring)**
Multiple RLVR implementations use a two-component reward:
- Correctness: 1.0 for correct answer, 0.0 otherwise
- Format adherence: 0.1 for proper `####` formatting even when answer is wrong, 0.0 for no format

This tiered scheme (1.0 / 0.1 / 0.0) is the most common auxiliary reward for GSM8K RL training.

*Sources*: GSM8K-RLVR (Mohammadjafari80, GitHub), veRL framework GSM8K example, Unsloth RL documentation, Tulu3-inspired RLVR implementations.

**Finding 2: Process reward models (PRMs)**
Math-Shepherd (Wang et al., 2024) trains a separate model to score each reasoning step. Combined with PPO, it improved Mistral-7B from 77.9% to 84.1% on GSM8K. DeepSeek-Math (Shao et al., 2024) found GRPO with process supervision (GRPO+PS) outperforms outcome supervision (GRPO+OS).

However, PRMs require a separately trained verifier model. **Not feasible** for our setup — we have no external model and no budget to train one.

*Sources*: Wang et al. (2024) "Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations" (ACL 2024). Shao et al. (2024) "DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models."

**Finding 3: Proximity-based partial credit**
Unsloth's RL documentation describes a proximity-based reward function where answers closer to the gold get more reward (e.g., predicting 9 instead of 10 scores higher than predicting 3). This provides denser signal than binary correctness.

*Source*: Unsloth RL documentation.

**Finding 4: Overlong reward shaping**
DAPO (Yu et al., 2025) introduces overlong reward shaping — penalizing responses that exceed a maximum length. This stabilizes training by discouraging the model from generating unnecessarily long reasoning chains that could be exploited for higher process rewards.

*Source*: Yu et al. (2025) "DAPO: An Open-Source LLM Reinforcement Learning System at Scale" (NeurIPS 2025).

#### RQ2: Weaknesses of binary correctness reward

1. **Sparse gradient signal**: At 15% accuracy, most samples get reward 0.0. With mean subtraction across 16 samples, many examples contribute zero gradient (all 0s → mean 0 → advantage 0 for all samples).

2. **No partial credit**: A response with correct reasoning but arithmetic error gets the same 0.0 as a gibberish response. The model gets no learning signal about what it did right.

3. **Format-reasoning conflation**: Binary reward conflates two independent skills: (a) producing the `#### <number>` format, and (b) getting the math right. A separate format signal would let the model learn formatting independently from reasoning.

4. **Reward hacking risk with dense rewards**: Gao et al. (2024) show that learned reward models can be exploited — models repeat correct steps for higher cumulative reward without improving accuracy. Rule-based rewards avoid this since they don't have an exploitable gradient.

*Sources*: Gao et al. (2024) "On Designing Effective RL Reward at Training Time for LLM Reasoning" (arXiv: 2410.15115). DeepSeek-Math observations on GRPO improving Maj@K but not Pass@K.

#### RQ3: Reward categories and feasibility

| Category | Examples | Feasible? | Reason |
|----------|----------|-----------|--------|
| **Format (rule-based)** | `####` presence, answer extraction | Yes | Text-in, float-out; no external model; pure regex |
| **Process (model-based)** | Math-Shepherd PRM, step-level scores | No | Requires trained verifier model |
| **Process (heuristic)** | Count reasoning steps, check calculator use | Yes | Rule-based proxy for process quality |
| **Outcome (proximity)** | Numeric distance to gold answer | Yes | Requires extracting and comparing numbers |
| **Outcome (partial credit)** | Tiered scoring based on format + closeness | Yes | Combines format and outcome |
| **Length-based** | Penalize overlong, reward structured length | Yes | Simple token/line counting |

Feasible approaches are all rule-based (no external model), operate on the decoded text, and return a single float.

#### RQ4: Observable effects in 467 steps

Rewards that give signal from step 1 (before the model is accurate):
- **Format reward**: ~11% of responses lack `####` — format reward gives signal on every such sample immediately
- **Proximity reward**: ~74% of responses have the format but wrong answer — proximity gives graded signal on all of these
- **Calculator usage**: Mixed usage in baseline — reward could push toward consistent tool use

Rewards unlikely to help in 467 steps:
- **Process rewards requiring a verifier**: Training a verifier requires separate data and compute
- **Very fine-grained step scoring**: Model may not have enough capacity or training time to respond to step-level signals

### Candidate Reward Designs

**Candidate 1: Format Compliance Reward**
- **Target**: Reward producing the `#### <number>` answer format
- **Logic**: 1.0 if response contains `#### (-?[0-9.,]+)` pattern, 0.0 otherwise
- **Expected effect**: Reduces format failure from ~11% toward 0%; decouples format learning from reasoning learning
- **Literature**: GSM8K-RLVR tiered scoring (Tulu3-style), veRL framework, multiple RLVR implementations
- **Feasibility**: Pure regex on response text. Composes trivially with binary correctness (sum).
- **Gradient signal**: Immediate — fires on every response, gives differentiation between format-compliant and non-compliant samples

**Candidate 2: Numeric Proximity Reward (partial credit)**
- **Target**: Reward answers that are numerically close to the gold answer
- **Logic**: If response is parseable (has `#### <number>`), compute `proximity = max(0, 1 - |predicted - gold| / (|gold| + 1))`. Returns a float in [0, 1]. Correct answers get 1.0, close answers get partial credit, far answers get ~0.
- **Expected effect**: Provides graded signal for the ~74% of responses that format correctly but answer wrong. Model can learn "warmer/colder" rather than only "right/wrong."
- **Literature**: Unsloth proximity-based reward, general reward shaping theory (Ng et al., 1999)
- **Feasibility**: Requires extracting predicted number (already done by `extract_answer()`) and gold number from conversation. Simple arithmetic.
- **Gradient signal**: Dense — gives non-zero reward on most parseable responses, creating variance in the 16 samples even when none are correct

**Candidate 3: Calculator Usage Reward**
- **Target**: Reward use of calculator tool (`<|python_start|>...<|python_end|>`)
- **Logic**: 1.0 if response contains `<|python_start|>` tag, 0.0 otherwise
- **Expected effect**: Encourages consistent calculator use, reducing arithmetic errors (a known GSM8K failure mode per Wei et al. 2022)
- **Literature**: Wei et al. (2022) identify calculation error as one of three main GSM8K failure modes. GSM8K gold solutions use calculator extensively.
- **Feasibility**: Simple string match. Composes with other rewards.
- **Risk**: May over-reward calculator use even when reasoning is wrong. Could encourage inserting meaningless calculator calls.

**Candidate 4: Reasoning Structure Reward**
- **Target**: Reward multi-step reasoning (presence of step markers like newlines + arithmetic operations)
- **Logic**: Count reasoning steps (newline-separated statements containing numbers or operations). Reward = min(step_count / target_steps, 1.0) where target_steps is tuned (e.g., 3).
- **Expected effect**: Encourages structured step-by-step reasoning instead of jumping to answer
- **Literature**: Chain-of-Thought (Wei et al., 2022) shows multi-step reasoning improves accuracy. DAPO's overlong reward shaping addresses the inverse problem.
- **Feasibility**: Heuristic counting, no external model.
- **Risk**: Reward hacking via padding with meaningless steps (flagged by Gao et al. 2024). Harder to tune threshold.

### Candidate Assessment

| Candidate | Signal density | Hack risk | Implementation complexity | Literature support |
|-----------|---------------|-----------|--------------------------|-------------------|
| 1. Format Compliance | High (fires on every sample) | Low (binary, hard to game) | Very low (regex) | Strong (multiple RLVR implementations) |
| 2. Numeric Proximity | High (graded on all parseable) | Low (tied to gold answer) | Low (arithmetic) | Moderate (Unsloth, reward shaping theory) |
| 3. Calculator Usage | Medium (binary per sample) | Medium (meaningless calls) | Very low (string match) | Moderate (Wei et al. error taxonomy) |
| 4. Reasoning Structure | Medium (heuristic counting) | High (padding with steps) | Medium (parsing heuristic) | Moderate (CoT literature) |

**Recommendation for selection (step 1.12)**: Candidates 1 and 2 are the strongest pair — they target different weaknesses (format vs reasoning quality), have low hack risk, and provide complementary gradient signal. Candidate 1 helps the ~11% with format failure. Candidate 2 helps the ~74% with wrong answers. Together, they cover ~85% of failure cases.

### Sources

1. Shao et al. (2024). "DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models." arXiv:2402.03300.
2. Wang et al. (2024). "Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations." ACL 2024. arXiv:2312.08935.
3. Gao et al. (2024). "On Designing Effective RL Reward at Training Time for LLM Reasoning." arXiv:2410.15115.
4. Yu et al. (2025). "DAPO: An Open-Source LLM Reinforcement Learning System at Scale." NeurIPS 2025. arXiv:2503.14476.
5. Wei et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022.
6. Mohammadjafari80. "GSM8K-RLVR." GitHub. https://github.com/Mohammadjafari80/GSM8K-RLVR
7. veRL documentation. "GSM8K Example." https://verl.readthedocs.io/en/latest/examples/gsm8k_example.html
8. Unsloth documentation. "Reinforcement Learning (RL) Guide." https://docs.unsloth.ai/get-started/reinforcement-learning-rl-guide
9. Karpathy. "Introducing nanochat." GitHub discussions/1. https://github.com/karpathy/nanochat/discussions/1
