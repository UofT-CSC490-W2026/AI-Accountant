# Context Window Extension: Literature Review

## Why Train-Short-Then-Extend Works

Training a language model at reduced sequence length before extending to the target length is a well-studied approach with two primary advantages:

1. **Computational savings**: Self-attention cost is quadratic in sequence length — attention alone is ~16x cheaper at 512 vs 2048 tokens. The total per-step speedup is smaller (FFN layers scale linearly), but training at reduced sequence length is significantly cheaper overall, allowing the model to see more tokens in the same wall-clock time.

2. **Curriculum effect**: Starting with short contexts forces the model to learn local patterns (syntax, common phrases, short-range dependencies) before tackling long-range dependencies. GrowLength (Jin et al., 2023) demonstrates that this curriculum produces lower loss than fixed-length training at the same compute budget — a 70M model trained with progressive growth matched the loss of a 160M model trained at fixed length.

SkyLadder (NeurIPS 2025) further confirms that models pretrained with shorter contexts consistently outperform long-context models on standard benchmarks, while still acquiring long-context capability once exposed to longer sequences.

## Known Pitfalls

### Loss Spike on Context Change

When sequence length increases abruptly, models experience a transient loss spike. GrowLength observes that "substantial difference between consecutive training window sizes can lead to dramatic loss rising." The spike occurs because:

- The model encounters positional patterns it hasn't seen (positions 512–2048)
- Attention patterns must adapt to a 4x larger context window
- Batch statistics shift (more tokens per sequence, different padding ratios)

GrowLength reports that with their recommended 2x per-stage schedule, "the loss transition is smooth" — no visible spike. However, when jumping directly from 128→1024 (8x), they observe "dramatic loss rising." They provide no quantitative data on recovery duration for any jump ratio. SkyLadder finds that monotonic short-to-long expansion avoids the worst spikes; cyclic schedules (long→short→long) cause more severe disruption.

### Forgetting

If extension training runs too long relative to the short-context phase, the model may degrade on capabilities learned during short-context training. ProLong (Gao et al., 2024) mitigates this by deliberately mixing short-context examples (40%) alongside long-context examples during extension. Our setup does not do this — nanochat at `seq_len=2048` draws contiguous 2048-token chunks, with no short-sequence mixing. Keeping the extension phase short relative to the base phase limits exposure to this risk.

## Standard Ratios

| Paper | Short Length | Target Length | Ratio | Notes |
|-------|-------------|---------------|-------|-------|
| GrowLength | 128 | 1024 | 8x | Multi-stage: 128→256→512→1024 |
| SkyLadder | 32 | 8192 | 256x | Linearly increasing schedule (stepwise in 1K increments) |
| ProLong | 8192 | 512K | 64x | Continued pretraining from Llama-3-8B |
| **Ours** | **512** | **2048** | **4x** | Single-stage jump (assignment specifies one resume) |

We use a single-stage jump because the assignment specifies "resume training from the short checkpoint with sequence length 2048" — one resume, one target length. GrowLength uses multi-stage with 2x per jump; SkyLadder uses continuous growth. Our 4x single-stage jump is larger than GrowLength's 2x per-stage ratio. GrowLength reports 2x jumps are "smooth" while 8x jumps cause "dramatic loss rising" — our 4x falls between, so we expect a spike but have no quantitative recovery data. We run a generous extension phase (500 steps) with frequent checkpointing to observe the actual recovery trajectory. RoPE helps: new positions require no weight changes, only a recomputed frequency cache.

## Target Length: 2048

The assignment requires resuming with `seq_len=2048` (R3). This is also nanochat's default `--max-seq-len`, so no RoPE interpolation or rescaling is needed — we are returning to the model's native context length, not extrapolating beyond it.

## Short Sequence Length Choice: 512

GrowLength validates 2x per-stage jumps (128→256→512→1024) as the established baseline for progressive context growth. However, a 2x jump from our target (1024→2048) yields negligible cost savings — the short phase would be nearly as expensive as full-length training, defeating the purpose of train-short-then-extend.

We therefore need to exceed the 2x baseline, which means the starting length must be grounded independently. Salhan et al. (2025) ("What is the Best Sequence Length for BabyLM?") systematically test 125M-parameter models across sequence lengths {64, 128, 256, 512, 1024, 2048, 4096, 8192}. Their findings for the 256–512 range on a 125M OPT model:

| Metric | 256 | 512 |
|--------|-----|-----|
| BLiMP (syntax) | 73.88% | 71.9% |
| BLiMP Supplement | 67.20% | 59.60% |
| Entity Tracking | 32.42% | 26.80% |

Both lengths are competitive; the paper recommends 512 as "a safe and efficient baseline across both architectures" at 35–44% of full training cost. We choose `max_seq_len=512`:

1. **Grounded starting point**: 512 is independently validated by BabyLM for models at our scale (~125M params), ensuring the model learns robust patterns during the short phase.
2. **Smallest viable extrapolation**: The resulting 4x single-stage jump (512→2048) is the smallest ratio beyond GrowLength's 2x baseline that still delivers meaningful compute savings.
3. **RoPE compatibility**: Nanochat uses RoPE with `persistent=False` buffers — no positional embedding weights are saved to the checkpoint. Changing `--max-seq-len` on resume simply recomputes the RoPE cache at the new length.
4. **Assignment corroboration**: The assignment suggests "e.g. 512" as the short sequence length.

## References

1. Jin, H., Han, X., Yang, J., Jiang, Z., Chang, C.-Y., & Hu, X. (2023). *GrowLength: Accelerating LLMs Pretraining by Progressively Growing Training Length*. arXiv:2310.00576. https://arxiv.org/abs/2310.00576

2. Zhu, T., Liu, Q., Wang, H., Chen, S., Gu, X., Pang, T., & Kan, M.-Y. (2025). *SkyLadder: Better and Faster Pretraining via Context Window Scheduling*. NeurIPS 2025. arXiv:2503.15450. https://arxiv.org/abs/2503.15450

3. Gao, T., Wettig, A., Yen, H., & Chen, D. (2024). *How to Train Long-Context Language Models (Effectively)*. ACL 2025. arXiv:2410.02660. https://arxiv.org/abs/2410.02660

4. Salhan, S., Diehl Martinez, R., Goriely, Z., & Buttery, P. (2025). *What is the Best Sequence Length for BabyLM?* BabyLM Workshop @ EMNLP 2025. arXiv:2510.19493. https://arxiv.org/abs/2510.19493
