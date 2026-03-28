# Design: Rewards C, D, and E

## Overview

This document specifies Rewards C, D, and E — three additional reward functions designed post-P3 from exploratory data analysis of the pre-P3 RL runs. These are the "informed" rewards (R2), grounded in both observed failure patterns and established research on reward design for mathematical reasoning.

Each reward function follows the interface `reward(conversation, assistant_response) -> float` and composes with the existing rewards via summation.

### Design Rationale

Given the constraint of rule-based rewards with no learned components, we designed auxiliary signals grounded in observed failure modes. These are inspired by — but substantially simpler than — the process supervision and KL regularization used in production systems. The state of the art (Lightman et al. 2023, Math-Shepherd 2024, DeepSeek-R1 2025) uses step-level process reward models and KL divergence penalties built into the optimizer. Our rewards operate at the response level using surface-level heuristics — a pragmatic compromise that addresses the specific failure modes observed in our EDA within the constraints of our training interface and compute budget.

---

## Part I: EDA Findings and Research Grounding for Directions

### The Core Finding: The Model Does Not Read the Question

Exploratory data analysis of 1319 test problems x 8 samples x 4 runs revealed a critical finding: **82% of "correct" responses solve a completely different GSM8K problem** that coincidentally produces the same numeric answer.

Examples:
- Question: "James decides to run 3 sprints 3 times a week..." (gold=5)
  Response: "Bethany can run 10 laps... Quinn can run 7 - 2 = 5" → `#### 5` (marked correct)
- Question: "Toula went to the bakery and bought pastries..." (gold=12)
  Response: "Kira bought 3 apples, 5 bananas, and 6 oranges... 14 - 2 = 12" → `#### 12` (marked correct)

This is consistent across all 4 runs — the alignment rate stays at ~17-18% regardless of reward configuration.

### This is Reward Hacking

Our finding is a specific instance of **reward hacking** (Goodhart's Law applied to RL): the model exploits the reward function's structure rather than learning the intended behavior. Lilian Weng (2024) surveys this phenomenon in the RLHF context, and Wen et al. (2024) term the related phenomenon **"U-Sophistry"** — models optimized by outcome-based rewards learn to produce outputs that appear correct without being correct.

In our case, the binary correctness reward checks only `#### <number>` against the gold answer. A response that solves an entirely different problem but produces the right number receives the same 1.0 reward. The model learned to generate GSM8K-style solutions that produce specific integers, without conditioning on the input — the reward function cannot distinguish this from genuine problem-solving.

This connects directly to the distinction Uesato et al. (2022) and Lightman et al. (2023) draw between **outcome-based** and **process-based** supervision:

> "Models trained with outcome supervision regularly use incorrect reasoning to reach the correct final answer, and process supervision has been shown to mitigate this misaligned behavior." — Lightman et al. (2023)

Our EDA quantifies this at scale: outcome-only supervision (binary correctness) produces an 82% rate of correct-answer-wrong-reasoning.

### Quantifying the Problem

| Run | Correct Responses | Question-Aligned | Misaligned | Random Collision |
|-----|-------------------|------------------|------------|-----------------|
| Baseline | 997 | 176 (17.7%) | 821 (82.3%) | 1.06% |
| + Format (A) | 1236 | 222 (18.0%) | 1014 (82.0%) | 1.06% |
| + Proximity (B) | 1023 | 188 (18.4%) | 835 (81.6%) | 1.07% |
| A + B | 1203 | 204 (17.0%) | 999 (83.0%) | 1.07% |

Pass@1 is 9.7% for baseline, but random collision (drawing from the model's answer distribution and checking against gold) would give only 1.06%. The 9x gap suggests partial input conditioning — likely answer magnitude cues — but not genuine problem-solving.

### Six Failure Modes Identified

| # | Failure Mode | % of Errors (Baseline) | Description |
|---|---|---|---|
| 1 | Token soup / gibberish | 32.1% | Random tokens: "Mesothelioma Garvey diplomatsCrime..." |
| 2 | Wrong problem, no format | 38.6% | Coherent GSM8K solution to a different question, no `####` |
| 3 | Wrong problem, formatted, wrong number | 18.1% | Solves different problem, has `####`, number doesn't match |
| 4 | Wrong problem, formatted, right number | ~82% of "correct" | Solves different problem, `####` matches gold by coincidence |
| 5 | Near-miss | 10.9% | Parseable number close to gold but not exact |
| 6 | Starts coherent, degenerates | subset of 1 | Begins a real sentence then collapses into token soup |

### Three Structural Gaps in Binary Reward

Karpathy's binary reward has three structural properties that enable these failure modes:

1. **No input grounding signal**: The reward checks only `#### <number>` against gold. There is no incentive to read the input. This is the **reward hacking vulnerability** — the proxy reward (answer match) diverges from the true objective (solving the given problem).

2. **No coherence signal**: Gibberish and coherent wrong answers both receive 0.0. There is no gradient from gibberish toward coherent text, which is a prerequisite for correct reasoning. Standard RLHF addresses this with a **KL divergence penalty** against a reference policy (Ouyang et al., 2022; Stiennon et al., 2020), but our GRPO-style setup (following Karpathy's baseline) omits this.

3. **Sparse signal**: With ~10-15% accuracy, most examples yield zero advantage → zero gradient. The model receives no learning signal on ~85% of examples.

Rewards A and B partially addressed gap 3 (denser signal) but did not address gaps 1 and 2. C, D, and E target these remaining gaps.

### Research-Grounded Directions

Our EDA identifies two root causes needing correction, each with established research precedent:

**Direction 1: Anti-degeneration (→ Reward C)**
- 32% of responses are gibberish — the model degenerates during RL without a coherence constraint
- **Research basis**: KL penalty in RLHF prevents policy from deviating into incoherent text (Ouyang et al., 2022; Stiennon et al., 2020). DeepSeek-R1 (2025) uses a **format reward** alongside accuracy to maintain output structure. The FIRE framework (OpenReview, 2024) proposes fine-grained rewards to address text degeneration in RL. Our setup lacks any equivalent — C fills this role.

**Direction 2: Input grounding / faithfulness (→ Rewards D, E)**
- 82% of "correct" responses solve a different problem — the model doesn't condition on the input
- **Research basis**: Nan et al. (EACL 2021) establish **entity-level factual consistency** metrics for summarization: checking that entities in the output are grounded in the source document. The Entity Hallucination Index (EHI) has been used as a direct RL reward signal for entity-grounded generation (arXiv 2507.22744). Fu et al. (2025) show that **multi-component reward shaping** mitigates reward hacking by preventing the policy from exploiting any single signal. Our D and E adapt these faithfulness metrics from summarization to math QA.

### Why Rule-Based Rewards

DeepSeek-R1 (2025) deliberately chose **verifiable, rule-based rewards** over neural reward models for math reasoning:

> "We chose to avoid using neural reward models... due to issues with reward hacking in larger-scale RL training runs. If you train the LLM for long enough, it will eventually figure out an exploit for the reward model." — DeepSeek-R1

Our C, D, and E follow this principle: all are deterministic, rule-based functions with no learned components. This also aligns with Ng et al.'s (1999) framework for reward shaping — additional reward signals that guide learning without changing the optimal policy. While our rewards are not formally potential-based (a requirement for strict policy invariance), they satisfy the practical properties identified by Fu et al. (2025): **bounded** [0,1], **gradually varying**, and **centered** relative to the mixed population of responses seen during training.

---

## Part II: Reward Specifications

## Reward C: Coherence

### Research Grounding

In standard RLHF, the **KL divergence penalty** `β · D_KL(π_θ || π_ref)` prevents the policy from degenerating (Ouyang et al., 2022; Stiennon et al., 2020). Without it, "the optimization can start to generate text that is gibberish but fools the reward model to give a high reward" (HuggingFace RLHF blog). Our GRPO setup has no KL penalty — C serves as a lightweight, output-side proxy for the same anti-degeneration effect.

DeepSeek-R1 (2025) uses a complementary approach: a **format reward** that enforces structural properties of the output (e.g., requiring `<think>` tags, proper formatting). Our Reward A (format compliance) partially fills this role by rewarding `####` markers, but does not penalize gibberish directly. C completes this coverage.

The approach of using structural heuristics to detect degenerate text is related to the **FIRE** framework (Fine-grained Reward for RL in text generation), which proposes moving from sentence-level to token-level reward signals to address degeneration.

### Target Behavior
Reward the model for producing coherent English text with mathematical structure, penalizing gibberish / token soup.

### Specification

```python
import re

def reward_coherence(conversation, assistant_response):
    text = assistant_response.strip()
    if len(text) < 20:
        return 0.0

    tokens = text.split()
    if len(tokens) < 3:
        return 0.0

    # --- Anti-gibberish signals ---
    # CamelCase / concatenated token detection
    camel_count = 0
    for t in tokens:
        clean = re.sub(r'[^a-zA-Z]', '', t)
        if len(clean) > 3:
            internal_caps = sum(1 for c in clean[1:] if c.isupper())
            if internal_caps >= 1:
                camel_count += 1
    camel_frac = camel_count / len(tokens)
    mega_frac = sum(
        1 for t in tokens if len(re.sub(r'[^a-zA-Z]', '', t)) > 15
    ) / len(tokens)

    # --- Pro-coherence signals ---
    sentence_breaks = len(re.findall(r'[.?!]\s+[A-Z]', text))
    has_sentences = min(1.0, sentence_breaks / 2)
    has_equations = bool(re.search(r'\d+\s*[+\-*/=]\s*\d+', text))
    num_count = len(re.findall(r'\b\d+\b', text))
    has_numbers = min(1.0, num_count / 3)
    math_words = len(re.findall(
        r'\b(?:so|therefore|thus|if|then|each|total|per|more|less|than|'
        r'how|many|much|left|remaining|bought|sold|gave|has|have|had|'
        r'gets|earned|paid|cost|spent|times|twice|half)\b',
        text, re.I
    ))
    math_word_score = min(1.0, math_words / 3)

    # --- Combine ---
    anti_gibberish = (
        0.60 * (1.0 - min(1.0, camel_frac * 4))
        + 0.40 * (1.0 - min(1.0, mega_frac * 5))
    )
    pro_coherence = (
        0.30 * has_sentences
        + 0.35 * (0.5 * float(has_equations) + 0.5 * has_numbers)
        + 0.35 * math_word_score
    )
    score = 0.4 * anti_gibberish + 0.6 * pro_coherence
    return max(0.0, min(1.0, score))
```

### Empirical Calibration (on baseline eval, n=10,462)

| Response Type | Mean C | Median C |
|---|---|---|
| Correct (n=997) | 0.961 | 1.000 |
| Wrong + parseable (n=3,197) | 0.969 | 1.000 |
| Wrong + unparseable (n=6,268) | 0.454 | 0.400 |

### Limitations

C is a domain-specific heuristic, not a general coherence measure. It rewards "looks like a GSM8K solution" (math words, equations, sentence structure) rather than pure linguistic quality. A coherent paragraph about dogs would score ~0.3 — the same as gibberish. For GSM8K-specific RL this is acceptable (we want math-like responses), but it is not a transferable coherence metric.

### Failure Modes Addressed
- Mode 1 (token soup): directly penalized
- Mode 6 (starts coherent, degenerates): partially penalized

---

## Reward D: Entity Grounding

### Research Grounding

Nan et al. (EACL 2021) introduce **entity-level factual consistency** as a metric for abstractive summarization: they check whether entities in generated text are grounded in the source document, finding that entity hallucination is a primary failure mode. Their metric — fraction of output entities present in the source — directly inspired our implementation.

More recently, the **Entity Hallucination Index (EHI)** has been used as a direct RL reward signal for summarization fine-tuning (arXiv 2507.22744), demonstrating that entity-level overlap can serve as an effective reward for promoting input-grounded generation without requiring a learned reward model.

We adapt this from summarization (source document → summary) to math QA (question → response). The principle is identical: if the model's output discusses entities not present in the input, it is not faithfully engaging with the given problem.

This reward also functions as an **anti-reward-hacking auxiliary signal** in the spirit of multi-component reward design (Fu et al., 2025; ODIN, Chen et al., 2024). Binary correctness cannot distinguish "solves the right problem" from "produces the right number by coincidence." D adds an orthogonal signal that penalizes the latter.

### Target Behavior
Reward the model for mentioning the same entities (names, subjects) that appear in the question.

### Specification

```python
import re

def _get_entities(text):
    """Extract proper nouns: capitalized words not at sentence start, len > 2."""
    entities = set()
    sentences = re.split(r'[.!?]\s+', text)
    for sent in sentences:
        words = sent.split()
        for i, w in enumerate(words):
            clean = re.sub(r'[^a-zA-Z]', '', w)
            if clean and clean[0].isupper() and len(clean) > 2 and i > 0:
                entities.add(clean.lower())
    return entities

def reward_entity_grounding(conversation, assistant_response):
    question = conversation['messages'][0]['content']
    q_entities = _get_entities(question)
    if not q_entities:
        return 1.0  # no entities to check — conservative fallback
    r_entities = _get_entities(assistant_response)
    overlap = q_entities & r_entities
    return len(overlap) / len(q_entities)
```

### Formula
- **Output**: `|entities_in_response ∩ entities_in_question| / |entities_in_question|`
- Question about "Janet's ducks" → response mentions "Janet" → 1.0
- Question about "Janet's ducks" → response about "Bethany's laps" → 0.0
- Question with no proper nouns → 1.0 (conservative fallback)

### Limitations

- ~3-5% of GSM8K questions have no proper names → D gives 1.0 by default. Number Grounding (E) covers this gap.
- Entity extraction via capitalization heuristic may miss entities or produce false positives. A NER model would be more robust but violates the rule-based constraint.

### Failure Modes Addressed
- Mode 2 (wrong problem, no format): penalized — wrong entities
- Mode 3 (wrong problem, formatted, wrong number): penalized — wrong entities
- Mode 4 (wrong problem, formatted, right number): **directly penalized** — the core reward hacking mode

---

## Reward E: Number Grounding

### Research Grounding

Number grounding extends the entity-grounding principle to numerical values. While no prior work uses exactly this formulation as an RL reward for math, the underlying principle is established:

1. **Input-output faithfulness**: The same logic as entity grounding (Nan et al., 2021) applies — a response that does not reference the numbers from the question cannot be faithfully solving the given problem.

2. **Necessary condition for correct reasoning**: Uesato et al. (2022) show that outcome-based supervision misses reasoning errors. For a model to correctly solve a GSM8K problem, it MUST use the numbers provided. E enforces this as a verifiable necessary condition — complementing the outcome reward's sufficient condition (correct final answer).

3. **Complementarity with D**: D and E together form a **multi-signal grounding check** similar to multi-objective reward approaches (Fu et al., 2025; Sun et al., 2023). D catches entity mismatches (high precision, partial coverage). E catches number mismatches (lower precision due to collision, but universal coverage since every GSM8K question contains numbers).

### Target Behavior
Reward the model for using the specific numbers that appear in the question.

### Specification

```python
import re

def reward_number_grounding(conversation, assistant_response):
    question = conversation['messages'][0]['content']
    q_numbers = set(re.findall(r'\b\d+\.?\d*\b', question))
    if not q_numbers:
        return 1.0  # conservative fallback (rare in GSM8K)
    r_numbers = set(re.findall(r'\b\d+\.?\d*\b', assistant_response))
    overlap = q_numbers & r_numbers
    return len(overlap) / len(q_numbers)
```

### Formula
- **Output**: `|numbers_in_response ∩ numbers_in_question| / |numbers_in_question|`
- Question: "Janet's ducks lay **16** eggs... eats **3**..." → numbers = {16, 3, ...}
- Response uses 16, 3 in calculations → high score
- Response about "Bethany runs **10** laps" → 0/N = low score

### Limitations

- **Weaker signal than D**: Numbers collide frequently. Many problems use "2", "3", "10" — a response about a different problem may accidentally contain matching numbers. This is why D and E are complementary, not redundant.
- **Does not verify correct usage**: A response could mention the right numbers but combine them incorrectly. E checks necessary but not sufficient conditions for correctness.

### Failure Modes Addressed
- Mode 2 (wrong problem, no format): penalized — wrong numbers
- Mode 3 (wrong problem, formatted, wrong number): penalized — wrong numbers
- Mode 4 (wrong problem, formatted, right number): partially penalized (unlikely to contain all question numbers by collision)

---

## Part III: Design Properties

## Dependency Structure

```
C (Coherence)  ──→  D (Entity Grounding)
               ──→  E (Number Grounding)
```

C is the foundation: gibberish responses score 0 on D and E regardless, so there is no gradient for D and E to provide until the model produces coherent text. C pushes the model from gibberish → coherent English, which unlocks D and E's ability to push from coherent-but-wrong-problem → coherent-and-right-problem.

## Ablation Structure

| Config | Rewards | Tests |
|---|---|---|
| separate_c | correctness + C | Coherence alone |
| separate_d | correctness + D | Entity grounding alone |
| separate_e | correctness + E | Number grounding alone |
| combined_cd | correctness + C + D | C enables D |
| combined_cde | correctness + C + D + E | Full new stack |
| combined_all | correctness + A + B + C + D + E | Everything |

## Combined Reward Landscape (all 6 rewards)

| Response Type | Correctness | A (Format) | B (Proximity) | C (Coherence) | D (Entity) | E (Number) | Total |
|---|---|---|---|---|---|---|---|
| Correct, right problem | 1.0 | 1.0 | 1.0 | ~0.9 | ~0.9 | ~0.9 | ~5.7 |
| Correct, wrong problem | 1.0 | 1.0 | 1.0 | ~0.9 | ~0.0 | ~0.1 | ~4.0 |
| Wrong answer, right problem, formatted | 0.0 | 1.0 | partial | ~0.9 | ~0.9 | ~0.9 | ~3.7+ |
| Wrong answer, wrong problem, formatted | 0.0 | 1.0 | ~0.0 | ~0.9 | ~0.0 | ~0.1 | ~2.0 |
| Gibberish | 0.0 | 0.0 | 0.0 | ~0.2 | 0.0 | 0.0 | ~0.2 |

The key comparison: "Correct, wrong problem" (~4.0) vs "Wrong answer, right problem" (~3.7). With D+E, a response that engages with the right problem but gets the wrong answer scores nearly as well as one that hacks the reward. This creates gradient pressure toward input conditioning — even before achieving correctness.

## Constraint Verification

| Constraint | Reward C | Reward D | Reward E |
|---|---|---|---|
| Interface: `(conversation, response) -> float` | Yes | Yes | Yes |
| No external model | Yes (regex + heuristics) | Yes (regex only) | Yes (regex only) |
| Rule-based / verifiable | Yes | Yes | Yes |
| Bounded [0, 1] | Yes | Yes | Yes |
| Composable via summation | Yes (same scale) | Yes (same scale) | Yes (same scale) |
| Works with REINFORCE/GRPO | Yes | Yes | Yes |
| Signal from step 0 | Yes (gibberish exists) | Yes (wrong entities exist) | Yes (wrong numbers exist) |
| Computation cost | ~0.1ms | ~0.01ms | ~0.01ms |
| No external dependencies | Yes | Yes | Yes |

---

## References

- **Ng, Harada & Russell (1999)**. "Policy Invariance Under Reward Transformations: Theory and Application to Reward Shaping." ICML.
- **Stiennon et al. (2020)**. "Learning to Summarize with Human Feedback." NeurIPS.
- **Nan et al. (2021)**. "Entity-level Factual Consistency of Abstractive Text Summarization." EACL.
- **Ouyang et al. (2022)**. "Training Language Models to Follow Instructions with Human Feedback." NeurIPS (InstructGPT).
- **Uesato et al. (2022)**. "Solving Math Word Problems with Process- and Outcome-based Feedback." arXiv:2211.14275.
- **Lightman et al. (2023)**. "Let's Verify Step by Step." arXiv:2305.20050 (OpenAI PRM800K).
- **Wang et al. (2024)**. "Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations." ACL.
- **Wen et al. (2024)**. "Language Models Learn to Mislead Humans via RLHF." arXiv:2409.12822 (U-Sophistry).
- **Weng (2024)**. "Reward Hacking in Reinforcement Learning." Lil'Log.
- **Chen et al. (2024)**. "ODIN: Disentangled Reward Mitigates Hacking in RLHF."
- **DeepSeek-AI (2025)**. "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning." arXiv:2501.12948.
- **Fu et al. (2025)**. "Reward Shaping to Mitigate Reward Hacking in RLHF." arXiv:2502.18770 (PAR).
- **arXiv 2507.22744 (2025)**. "Reducing Hallucinations in Summarization via Reinforcement Learning with Entity Hallucination Index."
