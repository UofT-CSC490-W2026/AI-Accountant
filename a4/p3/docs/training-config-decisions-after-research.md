# Training Config: Decisions After Research

| # | Decision | Value | Justification | Confirmed |
|---|----------|-------|---------------|-----------|
| 1 | Picochat depth | 6 | Smallest depth with 3 heads for meaningful attention patterns; depth 4 has only 2 heads. Depth 8+ costs ~3x more with no benefit for context extension experiment. Pragmatic choice — no literature justification needed (assignment says "define your own config"). | |
| 2 | Data ratio | 10.5 (nanochat default) | Nanochat's LR, batch size scaling, and weight decay are tuned for this ratio; overriding it invalidates those hyperparameters. Below Chinchilla-optimal 20x (Hoffmann et al., 2022). | |
| 3 | Token budget | ~243.6M (0.24% of FineWeb-edu 100B) | Derived from 10.5 × 23.2M scaling params. This is the compute-optimal data portion under nanochat's scaling law. | |
| 4 | Stage 1: train to completion | ~929 iters (auto-compute) | Let nanochat auto-compute from scaling law. Stage 1 runs to natural completion with proper LR warmdown — not cut short. | |
| 5 | Stage 2: 500 extension steps | ~1429 total (auto + 500) | Continued pretraining beyond stage 1's horizon. GrowLength provides no quantitative recovery data for any jump ratio — 500 is a generous margin with save_every=50 to observe the actual trajectory. | |
| 6 | Stage 3: full from scratch | ~929 iters (auto-compute) | Same auto-computed default as stage 1 for fair comparison. Same model, same data budget, different seq_len. | |
| 7 | Auto batch size | 262,144 tokens | Power Lines formula (Bopt ∝ D^0.383) applied to depth 6 target tokens. | |
| 8 | Gradient accumulation | 16 steps at 512, 4 at 2048 | Follows from auto batch size (262,144) divided by device_batch_size=32 × seq_len. | |
| 9 | Fallback batch sizes | 65,536 or 131,072 | Override if auto-computed batch requires too many gradient accumulation steps. | |
| 10 | LR rewarm on resume | ~0 → ~0.70 | Stage 1 completes warmdown (LR ≈ 0). Stage 2 recalculates schedule for num_iterations=~1429; at step ~929, LR ≈ 0.70. Deliberate rewarm — same approach as ProLong for context extension. | |
| 11 | Checkpoint intervals | save_every=250 (Stage 1, 3), 50 (Stage 2) | Coarse for full training runs; fine for Stage 2 to capture loss spike and recovery trajectory. | |
| 12 | Model tags | pico-short (Stages 1-2), pico-full (Stage 3) | Stages 1-2 share tag — checkpoints coexist by step number. Stage 3 needs a distinct directory. | |
| 13 | Cost estimate | ~$1.65-3.25 on A100 | ~929 iters at 512 + 500 at 2048 + ~929 at 2048 + evals. Under $10 with reruns. | |
