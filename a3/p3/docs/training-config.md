# P3 Training Configuration

## Model: Picochat (depth=6)

| Parameter | Value | Source |
|-----------|-------|--------|
| Depth | 6 | Assignment default for picochat |
| Model dim | 384 | `depth * 64 = 384` (aspect_ratio=64) |
| Heads | 3 | `384 / 128 = 3` (head_dim=128) |
| Total params | 73,531,692 (~74M) | Verified from `GPT.num_scaling_params()` |
| Scaling params | 23,200,032 (~23M) | `transformer_matrices + lm_head` (nanochat convention) |

**Why depth=6**: The assignment specifies picochat. Depth 6 is the smallest model that still produces meaningful language (used in nanochat's own `runcpu.sh` demo). Depth 4 (~37M) converges too quickly for an interesting context extension experiment. Depth 8 (~126M) costs 3-4x more with diminishing pedagogical returns.

## Scaling Law and Data Budget

Nanochat uses `target_param_data_ratio=10.5` by default, meaning the training horizon in tokens is:

```
target_tokens = 10.5 * scaling_params = 10.5 * 23,200,032 ≈ 243,600,336
```

This ratio was derived empirically from nanochat's d12-d26 miniseries sweep (see `dev/LOG.md`, Jan 27 2026). It sits below the Chinchilla-optimal ratio of ~20 (Hoffmann et al., 2022) — deliberately over-training relative to Chinchilla because:

- Inference cost depends on model size, not training data. Smaller models benefit disproportionately from more data.
- At picochat scale, compute is cheap enough that the ratio barely matters for cost.
- Modern practice (Llama 3, Phi-3) trains at 100-1000x Chinchilla ratios. Our 10.5x is conservative.

We use nanochat's default 10.5 rather than overriding it — the codebase's hyperparameters (learning rate, batch size scaling, weight decay) are tuned for this ratio.

## Two-Stage Training Plan

### Stage 1: Short-Context Training (seq_len=512)

Train picochat at reduced sequence length to establish baseline capabilities.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `--max-seq-len` | 512 | Assignment suggestion; 4x ratio to target 2048 is well within safe range (see lit review) |
| `--num-iterations` | 750 | ~75% of total budget at short context (see split rationale below) |
| `--model-tag` | `pico-short` | Descriptive name for checkpoint directory |
| `--save-every` | 250 | Save at 250, 500, 750 for analysis |

### Stage 2: Extended-Context Training (seq_len=2048)

Resume from stage 1 checkpoint with extended sequence length.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `--max-seq-len` | 2048 | Nanochat's default; target context length |
| `--num-iterations` | 1000 | Total iterations (not additional — `--num-iterations` is absolute) |
| `--resume-from-step` | 750 | Resume from end of stage 1 |
| `--model-tag` | `pico-short` | Same tag — checkpoints coexist by step number |
| `--save-every` | 125 | Finer granularity to capture loss spike recovery |

**Stage 2 runs 250 additional iterations** (1000 total - 750 resume = 250 new steps). This is ~25% of the total budget.

### Stage Split Rationale: 75% Short / 25% Extended

| Factor | Reasoning |
|--------|-----------|
| Literature | GrowLength finds most learning happens during short-context phase. SkyLadder confirms short-context pre-training transfers well. |
| Cost efficiency | Training at seq_len=512 is ~4x cheaper per token than 2048 (quadratic attention cost). 75% of compute at the cheap length maximizes token throughput. |
| Extension needs | The model only needs to adapt attention patterns to longer contexts — not learn language from scratch. A few hundred steps suffices (GrowLength sees recovery within 100-300 steps). |
| Eval signal | 25% is enough for loss to recover from the spike and plateau, giving a clear before/after comparison. |

### `--num-iterations` Semantics

Nanochat's `--num-iterations` specifies the **total** step count, not additional steps on resume. When resuming from step 750 with `--num-iterations=1000`, training runs steps 750→1000 (250 new steps). This was verified in Phase 2 from `base_train.py:340`:

```python
num_iterations = target_tokens // total_batch_size
```

The step variable is set to the resume step, and the training loop runs `while step < num_iterations`.

## Batch Size

For single-GPU training on Modal, we let nanochat auto-compute the optimal batch size (`--total-batch-size=-1`). The Power Lines scaling law (Bopt ∝ D^0.383) gives:

- For depth=6 with 10.5 ratio: **auto batch size ≈ 262,144 tokens**
- At seq_len=512: `device_batch_size=32` → 16,384 tokens/fwd → 16 gradient accumulation steps
- At seq_len=2048: `device_batch_size=32` → 65,536 tokens/fwd → 4 gradient accumulation steps

If auto-compute produces batch sizes too large for reasonable gradient accumulation, we can override with `--total-batch-size=65536` or `--total-batch-size=131072`.

## Cost Estimate

| Stage | GPU | Est. Time | Est. Cost |
|-------|-----|-----------|-----------|
| Stage 1 (750 iters, seq_len=512) | A100 | ~5-10 min | $0.25-0.50 |
| Stage 2 (250 iters, seq_len=2048) | A100 | ~5-10 min | $0.25-0.50 |
| Eval (2 checkpoints) | A100 | ~2-5 min | $0.10-0.20 |
| **Total** | **A100** | **~15-25 min** | **$0.60-1.20** |

On A10G (cheaper per hour but slower): ~30-60 min, $0.55-1.10.

These estimates are rough — actual throughput depends on batch size, gradient accumulation, and whether evals run between stages. P3's total cost should be well under $5 even with failed runs and reruns.

## Param Count Reference Table

Verified by instantiating `GPT` on meta device (see Phase 2 + step 3.2.1):

| Depth | Dim | Heads | Total Params | Scaling Params |
|-------|-----|-------|-------------|----------------|
| 4 | 256 | 2 | 36,700,296 | 11,534,464 |
| **6** | **384** | **3** | **73,531,692** | **23,200,032** |
| 8 | 512 | 4 | 125,829,648 | 41,943,552 |
| 12 | 768 | 6 | 286,262,424 | 110,101,632 |

Note: Total params are inflated by value embeddings (~51% of total for d6). Scaling laws use `scaling_params` (transformer matrices + lm_head) which better predict loss.
