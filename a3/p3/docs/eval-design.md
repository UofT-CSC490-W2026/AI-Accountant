# Eval Design

## Purpose

Compare three training strategies to determine whether context extension (train short, extend later) is a viable alternative to training at full context from the start.

## Three Checkpoints

| Checkpoint | Tag | Step | Training Strategy |
|-----------|-----|------|-------------------|
| Short | `pico-short` | ~929 | ~929 iters at seq_len=512 (auto-computed, full scaling law budget) |
| Extended | `pico-short` | ~1429 | ~929 iters at 512, then 500 more at 2048 |
| Full | `pico-full` | ~929 | ~929 iters at seq_len=2048 from scratch |

Short and Extended share a model_tag because checkpoints coexist by step number. Full uses a separate tag.

## Three Evals

### 1. Positional Perplexity (custom — the main event)

Per-position cross-entropy loss on long documents, bucketed into 128-token windows (16 buckets for 2048 tokens).

**What it answers**: Can the model handle positions beyond its training length?

**Data source**: All documents from PG19 test split, each truncated to 2048 tokens. PG19 avoids data contamination (nanochat trains on FineWeb-edu) and is standard in context extension literature (PI, YaRN, LongRoPE).

**Expected results**:
- Short: catastrophic loss beyond position 512 (RoPE encounters unseen positions)
- Extended: smooth loss across full range (RoPE adapted during extension)
- Full: smooth loss across full range (trained at 2048 from the start)

**Implementation**: Use `model(input_ids, targets=targets, loss_reduction='none')` to get per-position loss. This goes through nanochat's logit softcap, producing loss values consistent with training.

### 2. BPB (built-in)

Bits per byte on train and val splits.

**What it answers**: Did overall language modeling quality change?

**How to run**: `python -m scripts.base_eval --eval bpb --model-tag <tag> --step <step>`

### 3. CORE (built-in — 22 tasks)

HellaSwag, ARC, PIQA, BoolQ, Winograd, SQuAD, COPA, and 15 others. Scored as centered accuracy above random baseline.

**What it answers**: Did general task capability change?

**How to run**: `python -m scripts.base_eval --eval core --model-tag <tag> --step <step>`

**Note**: At 74M params, many CORE tasks will be near random chance. HellaSwag, PIQA, BoolQ, and ARC-Easy are the most likely to show signal. The aggregate CORE score is still useful as a single number comparison.

## Success Criteria

### Part 1: Spike vs Smooth (short vs extended)

Proves context extension mechanically worked.

1. Short checkpoint: mean loss at positions 512–2048 is dramatically higher than at 0–512
2. Extended checkpoint: mean loss is smooth across the full range
3. The two curves are visually distinct — no statistical test needed

### Part 2: Cheap vs Expensive (extended vs full-from-scratch)

Proves the cheap training path is viable.

1. Extended checkpoint matches full-from-scratch on positional perplexity (smooth curves overlap)
2. Extended checkpoint is comparable on BPB (within noise)
3. Extended checkpoint is comparable on CORE (within noise)

If extended matches full, the cheap path wins — same result despite the base training phase being at 4x cheaper seq_len. If extended is worse, that's also a valid finding worth discussing.

## Output Deliverables

- **1 line plot**: positional perplexity with three lines (short, extended, full) + vertical line at position 512
- **1 BPB table**: train/val BPB for all three checkpoints
- **1 CORE table**: aggregate CORE score + per-task scores for all three checkpoints

## References

1. Chen, S., Wong, S., Chen, L., & Tian, Y. (2023). *Extending Context Window of Large Language Models via Positional Interpolation*. arXiv:2306.15595.
2. Peng, B., Quesnelle, J., Fan, H., & Shippole, E. (2023). *YaRN: Efficient Context Window Extension of Large Language Models*. ICLR 2024. arXiv:2309.00071.
3. Ding, Y., Zhang, L., Jia, C., et al. (2024). *LongRoPE: Extending LLM Context Window Beyond 2 Million Tokens*. arXiv:2402.13753.
