# P3 Specification: Context Window Extension

Every decision point required to run Part 3. Literature-grounded decisions cite references; pragmatic decisions state their reasoning.

---

## Experiment Design

Train picochat (a smaller nanochat) at reduced sequence length, extend to full context, and compare against training at full context from scratch. Three runs:

| Run | Strategy | Purpose |
|-----|----------|---------|
| Stage 1 → Stage 2 | Train at 512 → extend to 2048 | Cheap path |
| Stage 3 | Train at 2048 from scratch | Expensive path (control) |

---

## Literature-Grounded Decisions

### 1. Short sequence length = 512

GrowLength (Jin et al., 2023) validates 2x per-stage jumps (128→256→512→1024) as the established baseline for progressive context growth. A 2x jump from our target (1024→2048) yields negligible cost savings, defeating the purpose.

To exceed 2x, the starting length must be grounded independently. BabyLM (Salhan et al., 2025) tests 125M-parameter models across {64, 128, 256, 512, 1024, 2048, 4096, 8192} and recommends 512 as "a safe and efficient baseline across both architectures." The resulting 4x single-stage jump is the smallest extrapolation beyond GrowLength's 2x that still delivers meaningful savings. Assignment corroborates ("e.g. 512").

> **References**: Jin et al. (2023) arXiv:2310.00576; Salhan et al. (2025) arXiv:2510.19493

### 2. Single-stage 4x jump (512→2048)

The assignment specifies "resume training from the short checkpoint with sequence length 2048" — one resume, one target. GrowLength reports 2x jumps are "smooth" while 8x jumps cause "dramatic loss rising." Our 4x falls between — we expect a spike but have no quantitative recovery data. We run 500 extension steps with frequent saves to observe the actual trajectory.

> **Reference**: Jin et al. (2023) arXiv:2310.00576

### 3. Loss spike expected on context change

GrowLength observes that larger jumps between consecutive window sizes cause more dramatic loss rising. SkyLadder (Zhu et al., 2025) confirms monotonic short-to-long expansion avoids the worst spikes. GrowLength provides no quantitative recovery duration for any jump ratio.

> **References**: Jin et al. (2023) arXiv:2310.00576; Zhu et al. (2025) arXiv:2503.15450

### 4. Forgetting risk — unmitigated

ProLong (Gao et al., 2024) mitigates forgetting by mixing 40% short-context data during extension. Nanochat does not support this — at `seq_len=2048` it draws contiguous chunks with no short-sequence mixing. Only defense is keeping the extension phase short relative to the base phase.

> **Reference**: Gao et al. (2024) arXiv:2410.02660

### 5. Most learning happens during short-context phase

GrowLength and SkyLadder both find that short-context pretraining produces the bulk of capability. Extension mainly teaches the model to use longer positions — it adapts attention patterns, not language knowledge.

> **References**: Jin et al. (2023) arXiv:2310.00576; Zhu et al. (2025) arXiv:2503.15450

### 6. Data portion = 0.24% of dataset

Token budget of ~376M is 0.38% of the FineWeb-edu 100B-token corpus. This is the compute-optimal amount for a 35.8M scaling-parameter model under nanochat's 10.5x data ratio, which follows from Chinchilla-style scaling laws (Hoffmann et al., 2022). We use nanochat's default ratio because the codebase's hyperparameters (LR, batch size, weight decay) are co-tuned for it.

> **Reference**: Hoffmann et al. (2022) — Chinchilla scaling laws

### 7. Eval dataset = PG19 test split

PG19 avoids data contamination (nanochat trains on FineWeb-edu) and is standard in context extension literature (Positional Interpolation, YaRN, LongRoPE). Every document is far longer than 2048 tokens.

> **References**: Chen et al. (2023) arXiv:2306.15595; Peng et al. (2023) arXiv:2309.00071; Ding et al. (2024) arXiv:2402.13753

---

## Pragmatic Decisions (no literature justification needed)

### 8. Target sequence length = 2048

Assignment requirement R3: "Resume training from short checkpoint with sequence length 2048." Also nanochat's default `--max-seq-len`. No RoPE interpolation needed — returning to native context length.

### 9. Depth = 6 (dim=384, heads=3, ~136M total, ~35.8M scaling)

Assignment says "a smaller nanochat config you define." Depth 6 is the smallest config with 3 attention heads. Depth 4 has only 2 heads. Depth 8+ costs ~3x more with no benefit for the context extension experiment. Nanochat's own `runcpu.sh` uses depth 6 for demos. Far enough from nanochat's default depth 20 for P4 scaling law comparison.

### 10. Data ratio = 10.5 (nanochat default)

Nanochat's `target_param_data_ratio=10.5`, empirically derived from the d12-d26 miniseries sweep. Below Chinchilla-optimal ~20x. We don't override because LR schedule, batch size scaling, and weight decay are co-tuned for this ratio.

### 11. Stage 1: auto-compute iterations (~1433)

`target_tokens // total_batch_size = 375,732,000 // 262,144 ≈ 1433`. Let nanochat auto-compute — don't override `--num-iterations`. Stage 1 runs to natural completion with proper LR warmdown.

### 12. Stage 2: 500 extension steps (1433 + 500 = 1933 total)

Continued pretraining beyond Stage 1's natural horizon. GrowLength provides no quantitative recovery data — 500 is a generous margin. `save_every=50` gives 10 checkpoints to observe the spike and recovery curve. If loss plateaus early, extra steps are harmless.

### 13. Stage 3: auto-compute iterations (~1433)

Same model, same scaling ratio → same auto-computed iteration count as Stage 1. Fair comparison: same data budget, different sequence length.

### 14. Batch size = auto-compute (~262,144 tokens)

Power Lines scaling law (Bopt ∝ D^0.383). Fallback: `--total-batch-size=65536` or `131072` if gradient accumulation is excessive.

- At seq_len=512: device_batch_size=32 → 16,384 tokens/fwd → 16 grad accum steps
- At seq_len=2048: device_batch_size=32 → 65,536 tokens/fwd → 4 grad accum steps

### 15. Checkpoint intervals

- Stages 1, 3: `save_every=250` (coarse — 3-4 checkpoints for full training runs)
- Stage 2: `save_every=50` (fine — 10 checkpoints to capture loss spike and recovery)

### 16. Model tags

- `pico-short`: Stages 1 and 2 (checkpoints coexist by step number in same directory)
- `pico-full`: Stage 3 (separate directory)

### 17. GPU = A100

Compute budget decision. A100 provides sufficient memory and throughput for depth-6 at seq_len up to 2048.

### 18. LR rewarm on resume (~0 → ~0.70)

Stage 1 completes warmdown (LR ≈ 0). Stage 2 recalculates the schedule for `num_iterations=~1933`: warmdown starts at step ~967. At resume step ~1433, LR ≈ `(1933 - 1433) / (1933 - 967) ≈ 0.52`. This is a deliberate rewarm — the same approach ProLong uses for context extension. The jump may compound with the loss spike from the 4x context increase, but `save_every=50` tracks recovery.

### 19. Custom eval = positional perplexity

Per-position cross-entropy loss bucketed into 128-token windows (16 buckets for 2048 tokens). Directly measures whether the model can handle positions beyond its training length. Standard benchmarks (HellaSwag, PIQA) measure general capability, not context length.

### 20. Built-in evals = BPB + CORE

Free to run (already in nanochat). BPB measures overall language modeling quality; CORE (22 tasks) measures general task capability. Together they show whether extension affected anything beyond positional handling. At 74M params, most CORE tasks will be near random — HellaSwag, PIQA, BoolQ, ARC-Easy are most likely to show signal.

### 21. Eval bucketing = 128-token windows

16 buckets for 2048 tokens. Enough spatial resolution to see where the loss spike begins while averaging enough tokens per bucket for smooth curves.

### 22. Eval sample size = all PG19 test split documents

Full test split. Compute is cheap, no reason to subsample.

### 23. Success criteria

**Part 1 — Spike vs Smooth** (short vs extended): Short checkpoint shows catastrophic loss beyond position 512. Extended checkpoint is smooth across full range. Proves context extension mechanically worked.

**Part 2 — Cheap vs Expensive** (extended vs full-from-scratch): Extended checkpoint matches full-from-scratch on positional perplexity, BPB, and CORE. Proves the cheap path is viable. If it doesn't match, that's also a valid finding.

---

## Infrastructure (from Phase 1, not P3 decisions)

| Parameter | Value | Source |
|-----------|-------|--------|
| nanochat_ref | baseline-v0 | Phase 1 (tag on fork) |
| W&B project | 490-autobook-a3 | Phase 1 |
| Compute platform | Modal | Phase 1 |
| timeout_hours | 3 | Generous buffer |
| Training dataset | FineWeb-edu sample-100BT | Nanochat default |
| Checkpoint path | NANOCHAT_BASE_DIR | Phase 2 verification |

---

## Output Deliverables

- **1 line plot**: positional perplexity with 3 lines (short, extended, full) + vertical line at position 512
- **1 BPB table**: train/val BPB for all 3 checkpoints
- **1 CORE table**: aggregate + per-task scores for all 3 checkpoints
- **W&B runs**: p3-baseline-short, p3-baseline-extended, p3-baseline-full
- **Cost report**: actual GPU time and cost

---

## Cost Estimate

| Stage | GPU | Est. Time | Est. Cost |
|-------|-----|-----------|-----------|
| Stage 1 (~1433 iters, seq_len=512) | A100 | ~10-20 min | $0.40-0.80 |
| Stage 2 (500 iters, seq_len=2048) | A100 | ~10-20 min | $0.40-0.80 |
| Stage 3 (~1433 iters, seq_len=2048) | A100 | ~25-35 min | $1.00-1.40 |
| Eval (3 checkpoints × evals) | A100 | ~10-15 min | $0.40-0.60 |
| **Total** | **A100** | **~55-90 min** | **$2.20-3.60** |

Under $10 with failed runs and reruns.

---

## References

1. Jin, H., Han, X., Yang, J., Jiang, Z., Chang, C.-Y., & Hu, X. (2023). *GrowLength: Accelerating LLMs Pretraining by Progressively Growing Training Length*. arXiv:2310.00576.
2. Zhu, T., Liu, Q., Wang, H., Chen, S., Gu, X., Pang, T., & Kan, M.-Y. (2025). *SkyLadder: Better and Faster Pretraining via Context Window Scheduling*. NeurIPS 2025. arXiv:2503.15450.
3. Gao, T., Wettig, A., Yen, H., & Chen, D. (2024). *How to Train Long-Context Language Models (Effectively)*. ACL 2025. arXiv:2410.02660.
4. Salhan, S., Diehl Martinez, R., Goriely, Z., & Buttery, P. (2025). *What is the Best Sequence Length for BabyLM?* BabyLM Workshop @ EMNLP 2025. arXiv:2510.19493.
5. Hoffmann, J., Borgeaud, S., Mensch, A., et al. (2022). *Training Compute-Optimal Large Language Models*. NeurIPS 2022. arXiv:2203.15556.
6. Chen, S., Wong, S., Chen, L., & Tian, Y. (2023). *Extending Context Window of Large Language Models via Positional Interpolation*. arXiv:2306.15595.
7. Peng, B., Quesnelle, J., Fan, H., & Shippole, E. (2023). *YaRN: Efficient Context Window Extension of Large Language Models*. ICLR 2024. arXiv:2309.00071.
8. Ding, Y., Zhang, L., Jia, C., et al. (2024). *LongRoPE: Extending LLM Context Window Beyond 2 Million Tokens*. arXiv:2402.13753.
