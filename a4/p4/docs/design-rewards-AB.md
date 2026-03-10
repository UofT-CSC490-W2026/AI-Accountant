# Design: Rewards A and B

## Overview

This document specifies Reward A and Reward B — two additional reward functions designed pre-P3 from literature review and baseline behavior analysis. These are the "guessed" rewards (R1). Rewards C and D will be designed post-P3 from error analysis (R2).

Each reward function follows the interface `reward(conversation, assistant_response) -> float` and composes with the original binary correctness reward via summation.

---

## Reward A: Format Compliance

### Target Behavior
Reward the model for producing a parseable answer in the `#### <number>` format, independent of whether the answer is correct.

### Specification

```python
def reward_format_compliance(conversation, assistant_response):
    """
    Returns 1.0 if response contains #### <number>, 0.0 otherwise.
    Uses the same regex as the original GSM8K evaluation.
    """
    import re
    GSM_RE = re.compile(r"#### (\-?[0-9\.\,]+)")
    match = GSM_RE.search(assistant_response)
    return 1.0 if match else 0.0
```

### Formula
- **Input**: `assistant_response` (decoded text string)
- **Output**: `1.0` if `#### (-?[0-9.,]+)` regex matches anywhere in response, `0.0` otherwise
- **Scale**: Binary {0.0, 1.0} — same scale as original correctness reward

### Expected Effect
- Reduces format failure rate from ~11% toward 0%
- Decouples format learning from reasoning learning: model gets credit for attempting an answer even when wrong
- Creates gradient signal on examples where all 16 samples fail correctness (0/16 correct → all advantage = 0 with original reward only), as long as some samples have format and others don't

### Interaction with Original Reward
When summed: correct answer gets 2.0 (1.0 correctness + 1.0 format), wrong answer with format gets 1.0 (0.0 + 1.0), no format gets 0.0 (0.0 + 0.0). This creates a 3-tier ranking that is strictly better than binary for advantage computation — more variance across the 16 samples.

### Literature Justification (R14)
Format compliance reward is the standard auxiliary reward in RLVR (Reinforcement Learning from Verifiable Rewards) implementations for GSM8K:
- **GSM8K-RLVR** (Mohammadjafari80, GitHub): Uses tiered scoring where format compliance gets 0.1 points
- **veRL framework** (GSM8K example): Assigns 0.1 to incorrect-but-formatted answers, 0 to unformatted
- **Unsloth RL documentation**: Lists format adherence as a standard reward component
- **Tulu3-inspired implementations**: Consistently use format as an auxiliary signal

We use 1.0 instead of 0.1 for the format reward because our advantage computation uses simple mean subtraction (not z-score normalization). With 0.1 the format signal would be negligible relative to the 1.0 correctness signal. At 1.0, format compliance has equal weight to correctness, which is appropriate given that ~11% of failures are purely format-related.

### Why This Reward (and not alternatives)
- **Not Calculator Usage (Candidate 3)**: Calculator usage reward risks encouraging meaningless tool calls. Format compliance has no hack vector — either the format exists or it doesn't.
- **Not Reasoning Structure (Candidate 4)**: Step counting is a noisy proxy for reasoning quality and is susceptible to padding attacks (Gao et al., 2024). Format compliance is exact and deterministic.

---

## Reward B: Numeric Proximity

### Target Behavior
Reward the model for producing answers that are numerically close to the gold answer, giving partial credit rather than binary pass/fail.

### Specification

```python
def reward_numeric_proximity(conversation, assistant_response):
    """
    Returns a float in [0, 1] based on how close the predicted answer
    is to the gold answer. Requires the response to be parseable.
    Returns 0.0 if no answer is extractable.
    """
    import re
    GSM_RE = re.compile(r"#### (\-?[0-9\.\,]+)")

    # Extract gold answer from conversation
    assistant_message = conversation['messages'][-1]
    last_text_part = assistant_message['content'][-1]['text']
    ref_match = GSM_RE.search(last_text_part)
    if not ref_match:
        return 0.0
    ref_str = ref_match.group(1).strip().replace(",", "")

    # Extract predicted answer from response
    pred_match = GSM_RE.search(assistant_response)
    if not pred_match:
        return 0.0  # no parseable answer = no proximity reward
    pred_str = pred_match.group(1).strip().replace(",", "")

    try:
        ref_num = float(ref_str)
        pred_num = float(pred_str)
    except ValueError:
        return 0.0

    # Proximity: 1.0 when exact, decays toward 0.0 as distance increases
    distance = abs(pred_num - ref_num)
    denominator = abs(ref_num) + 1.0  # +1 avoids division by zero when gold is 0
    proximity = max(0.0, 1.0 - distance / denominator)
    return proximity
```

### Formula
- **Input**: `conversation` (contains gold answer), `assistant_response` (decoded text)
- **Output**: `max(0, 1 - |predicted - gold| / (|gold| + 1))` if both extractable, `0.0` otherwise
- **Scale**: Continuous [0.0, 1.0]
- **Properties**:
  - Exact match → 1.0
  - No parseable answer → 0.0
  - Close answer → high partial credit (e.g., gold=100, pred=95 → `1 - 5/101 ≈ 0.95`)
  - Far answer → low or zero credit (e.g., gold=100, pred=500 → `1 - 400/101 ≈ 0.0`)
  - Gold = 0 → denominator is 1, so pred=0 → 1.0, pred=1 → 0.0

### Expected Effect
- Provides graded signal for the ~74% of responses that have correct format but wrong answer
- Creates variance in the 16 samples even when 0/16 are exactly correct — samples with closer answers get higher reward, which translates to positive advantage after mean subtraction
- Encourages the model to improve incrementally toward correctness rather than only rewarding binary success

### Interaction with Original Reward
When summed: correct answer gets 2.0 (1.0 correctness + 1.0 proximity), close-but-wrong answer gets partial credit (0.0 + 0.95 = 0.95), far-wrong answer gets ~0.0, no format gets 0.0. Combined with Reward A: correct = 3.0, wrong-but-close-and-formatted = ~1.95, wrong-and-far-but-formatted = ~1.0, no format = 0.0. This creates a rich gradient landscape across the 16 samples.

### Literature Justification (R14)
- **Unsloth RL documentation**: Explicitly describes proximity-based reward where "models get more reward for closer answers (e.g., predicting 9 instead of 10 is better than 3)"
- **Reward shaping theory** (Ng et al., 1999): Potential-based reward shaping preserves optimal policy while accelerating learning. Our proximity reward is a potential function (closer to gold = higher potential) that provides dense gradient signal without changing which responses are optimal.
- **Sparse reward problem in RL**: Standard RL literature (Andrychowicz et al., 2017 "Hindsight Experience Replay") identifies sparse rewards as a fundamental challenge. Proximity rewards are a classic solution for continuous-valued goals.

### Why This Reward (and not alternatives)
- **Not Calculator Usage (Candidate 3)**: Calculator reward is binary and only addresses arithmetic errors. Proximity reward covers all types of wrong answers (arithmetic, setup, reasoning) with graded signal.
- **Not Reasoning Structure (Candidate 4)**: Reasoning structure reward is a proxy — it rewards a process without verifying the outcome. Proximity reward directly measures outcome quality, which is more aligned with the actual objective (correct answers).

### Complementarity with Reward A
Reward A and B target different failure modes:
- **A (Format)** addresses the ~11% that fail to produce `####` at all → binary signal for format compliance
- **B (Proximity)** addresses the ~74% that format correctly but get the wrong answer → graded signal for answer quality
- Together they cover ~85% of failures with non-overlapping targets
- They do not conflict: a response without `####` gets 0.0 from both A and B (A: no format, B: no extractable number). A response with `####` and wrong answer gets 1.0 from A and partial from B. A correct response gets 1.0 from both.

---

## Constraint Verification

| Constraint | Reward A | Reward B |
|-----------|----------|----------|
| Interface: `(conversation, response) -> float` | Yes | Yes |
| No external model | Yes (regex only) | Yes (regex + arithmetic) |
| Composable via summation | Yes (same scale as original) | Yes (same scale as original) |
| Works with REINFORCE | Yes (rule-based, no gradient through reward) | Yes (rule-based) |
| Signal in 467 steps | Yes (format failure exists from step 0) | Yes (wrong answers exist from step 0) |

---

## Sources

1. Mohammadjafari80. "GSM8K-RLVR." GitHub. https://github.com/Mohammadjafari80/GSM8K-RLVR
2. veRL documentation. "GSM8K Example." https://verl.readthedocs.io/en/latest/examples/gsm8k_example.html
3. Unsloth documentation. "Reinforcement Learning (RL) Guide." https://docs.unsloth.ai/get-started/reinforcement-learning-rl-guide
4. Gao et al. (2024). "On Designing Effective RL Reward at Training Time for LLM Reasoning." arXiv:2410.15115.
5. Ng et al. (1999). "Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping." ICML 1999.
6. Wei et al. (2022). "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022.
