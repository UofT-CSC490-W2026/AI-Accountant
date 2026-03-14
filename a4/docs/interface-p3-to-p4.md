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

### Checkpoints (Endpoints)

These are the three final checkpoints from P3's three training stages:

| Checkpoint | Model tag | Step | How it was trained | seq_len | Val BPB |
|------------|-----------|------|--------------------|---------|---------|
| Short | `pico-short` | 1433 | Trained from scratch at seq_len=512 for 1433 steps | 512 | 1.0586 |
| Extended | `pico-short` | 1933 | Resumed from Short, continued at seq_len=2048 for 500 more steps | 2048 | 1.0540 |
| Full | `pico-full` | 1433 | Trained from scratch at seq_len=2048 for 1433 steps | 2048 | 1.0499 |

**Recommended for P4**: `pico-full` @ step 1433 — strongest picochat model (best BPB and CORE).

### All Available Checkpoints

P3 saved checkpoints every 50 steps during training. These are all on the Modal Volume (`a3-checkpoints`) under `base_checkpoints/`. Each step has three files: `model_*.pt` (weights), `optim_*_rank0.pt` (optimizer state, only needed to resume training), `meta_*.json` (metadata).

**pico-short** (39 checkpoints):
- Steps 50–1433 (every 50): trained at seq_len=512 (Stage 1)
- Steps 1450–1933 (every 50): extension at seq_len=2048 (Stage 2)

**pico-full** (29 checkpoints):
- Steps 50–1433 (every 50): trained at seq_len=2048 from scratch (Stage 3)

If you need any of these checkpoints, ask Seonghyun — the Volume is on a personal Modal workspace so I'll download and share whichever ones you need.

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
