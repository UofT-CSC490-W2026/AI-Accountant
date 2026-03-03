# P3 → P4 Interface

> What P3 delivers to P4, and what P4 needs it for.

---

## What P3 Delivers

### Picochat Config

| Field | Value |
|-------|-------|
| Depth | 6 |
| Model dim | 384 |
| Attention heads | 3 |
| Total parameters | ~136M |
| Scaling parameters | ~35.8M |
| Short seq_len (stage 1) | 512 |
| Extended seq_len (stage 2) | 2048 |
| Nanochat branch/tag | `baseline-v0` |

### Checkpoints

| Checkpoint | Model tag | Step | seq_len | Path on Modal Volume |
|------------|-----------|------|---------|---------------------|
| Short-context | `pico-short` | 1433 | 512 | `/nanochat/base_checkpoints/pico-short/model_001433.pt` |
| Extended-context | `pico-short` | 1933 | 2048 | `/nanochat/base_checkpoints/pico-short/model_001933.pt` |
| Full (from scratch) | `pico-full` | 1433 | 2048 | `/nanochat/base_checkpoints/pico-full/model_001433.pt` |

### Key Metrics

| Metric | Short (1433) | Extended (1933) | Full (1433) |
|--------|-------------|-----------------|-------------|
| Val BPB | 1.0586 | 1.0540 | 1.0499 |
| PG19 aggregate CE | 4.4029 | 4.2980 | 4.0500 |
| PG19 aggregate PPL | 81.69 | 73.55 | 57.40 |
| CORE | N/A | 0.0766 | 0.0789 |

### Cost

| Field | Value |
|-------|-------|
| GPU type | A100-80GB |
| Total GPU-hours | 4.67 |
| Estimated cost | $29.77 |

### Tracking

| Field | Value |
|-------|-------|
| W&B run (short) | [p3-baseline-short](https://wandb.ai/seonghyun-ban-uoft/490-autobook-a3/runs/mpaiemt0) |
| W&B run (extended) | [p3-baseline-extended](https://wandb.ai/seonghyun-ban-uoft/490-autobook-a3/runs/woxwtud7) |
| W&B run (full) | [p3-baseline-full](https://wandb.ai/seonghyun-ban-uoft/490-autobook-a3/runs/wy8sw0zf) |
| W&B project | `490-autobook-a3` |

---

## What P4 Needs This For

### Scaling Law Prediction
- Use picochat scaling param count (35.8M) + val_bpb (1.0499 for full, or 1.0540 for extended) to predict nanochat (full-size, depth=20) performance
- Compare predicted vs actual after P4 training

### Emergent Abilities Comparison
- Find 10 questions nanochat answers but picochat cannot
- Use picochat checkpoint from P3 as the "smaller model" baseline
- Picochat checkpoints are on the Modal Volume under `pico-short` and `pico-full` model tags
