# P3 Training Configuration

## Model: Picochat (depth=6)

| Parameter | Value | Source |
|-----------|-------|--------|
| Depth | 6 | Our choice (see rationale below) |
| Model dim | 384 | `depth * 64 = 384` (aspect_ratio=64) |
| Heads | 3 | `384 / 128 = 3` (head_dim=128) |
| Total params | 73,531,692 (~74M) | Verified from `GPT.num_scaling_params()` |
| Scaling params | 23,200,032 (~23M) | `transformer_matrices + lm_head` (nanochat convention) |

**Why depth=6**: The assignment defines picochat as "a smaller nanochat config you define (reduced depth or width)." We choose depth 6 because it is the smallest model with enough heads (3) for meaningful attention patterns and is used in nanochat's own `runcpu.sh` demo. Depth 4 (~37M) has only 2 attention heads, limiting the model's ability to learn diverse attention patterns. Depth 8 (~126M) costs ~3x more with no pedagogical benefit.

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

**Data portion**: The assignment requires training picochat "on a portion of the dataset" (R1). Our token budget of ~244M is 0.24% of the FineWeb-edu 100B-token corpus. This portion is not arbitrary — it is the compute-optimal amount for a 23M scaling-parameter model under nanochat's 10.5x data ratio, which follows from Chinchilla-style scaling laws (Hoffmann et al., 2022).

## Three-Stage Training Plan

### Stage 1: Short-Context Training (seq_len=512)

Train picochat at reduced sequence length to completion. Let nanochat auto-compute the iteration count from the scaling law — don't override `--num-iterations`.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `--max-seq-len` | 512 | See lit review: BabyLM grounds 512 for models our scale; 4x jump is smallest viable extrapolation beyond GrowLength's 2x baseline |
| `--num-iterations` | (auto) ~929 | `target_tokens // total_batch_size`. Let nanochat compute — don't override |
| `--model-tag` | `pico-short` | Descriptive name for checkpoint directory |
| `--save-every` | 250 | Save at 250, 500, ~929 for analysis |

Stage 1 runs to natural completion, including proper LR warmdown. The model is fully trained at seq_len=512 when this stage ends.

### Stage 2: Extended-Context Training (seq_len=2048)

Resume from stage 1 checkpoint with extended sequence length. This is continued pretraining — additional steps beyond stage 1's natural training horizon, not carved from a shared budget.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `--max-seq-len` | 2048 | Nanochat's default; target context length |
| `--num-iterations` | ~1429 | ~929 (stage 1) + 500 extension steps |
| `--resume-from-step` | ~929 | Resume from end of stage 1 |
| `--model-tag` | `pico-short` | Same tag — checkpoints coexist by step number |
| `--save-every` | 50 | Fine granularity to capture loss spike and recovery trajectory |

**Stage 2 runs 500 additional steps.** GrowLength reports 2x jumps are "smooth" while 8x jumps cause "dramatic loss rising" but provides no quantitative recovery data. Our 4x jump falls between — we run generously (500 steps) with frequent saves (`save_every=50`) to observe the actual recovery curve. If loss plateaus early, the extra steps are wasted compute but harmless.

### Stage 3: Full-Context Baseline (seq_len=2048, from scratch)

Train picochat at full sequence length from step 0. This is the "expensive path" — the control group that context extension aims to match at lower cost.

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| `--max-seq-len` | 2048 | Same target as stage 2 |
| `--num-iterations` | (auto) ~929 | Same auto-computed default as stage 1 — fair comparison |
| `--model-tag` | `pico-full` | Distinct tag — separate checkpoint directory |
| `--save-every` | 250 | Same granularity as stage 1 |

**Why auto-compute (~929)**: Both Stage 1 and Stage 3 use the same model (depth=6) and the same default scaling ratio (10.5x), so nanochat auto-computes the same iteration count for both. The comparison is fair: same model, same data budget, different sequence lengths.

### `--num-iterations` Semantics

Nanochat's `--num-iterations` specifies the **total** step count, not additional steps on resume. When resuming from step ~929 with `--num-iterations=1429`, training runs steps 929→1429 (500 new steps). This was verified in Phase 2 from `base_train.py:340`:

```python
num_iterations = target_tokens // total_batch_size
```

The step variable is set to the resume step, and the training loop runs `while step < num_iterations`.

### Learning Rate Schedule on Resume

Nanochat uses a linear warmdown schedule (`base_train.py:349-359`): constant LR for the first half of training, then linear decay to zero (`warmdown_ratio=0.5`, `final_lr_frac=0.0`). The schedule is computed from the current run's `num_iterations`, not the original run's — so it **recalculates on resume**.

Stage 1 runs to natural completion, so its LR warmdown finishes properly (LR ≈ 0 at final step). On resume for Stage 2 with `--num-iterations=1429`, the schedule recalculates: warmdown starts at step ~714. Since we resume at step ~929, we're already past the warmdown midpoint — LR starts at roughly `(1429 - 929) / (1429 - 714) ≈ 0.70`.

This means LR jumps from ~0 (end of Stage 1) to ~0.70 (start of Stage 2) — an effective LR rewarm. This is deliberate: Stage 1 runs to natural completion with full warmdown, producing a converged model. Stage 2 then re-warms the LR for continued pretraining at the new context length — the same approach ProLong uses for context extension. Because Stage 1 finishes properly (not cut short), the rewarm is a clean transition, not an artifact. The jump may compound with the loss spike from the 4x context length increase, but 500 steps with `save_every=50` gives fine granularity to observe recovery.

## Batch Size

For single-GPU training on Modal, we let nanochat auto-compute the optimal batch size (`--total-batch-size=-1`). The Power Lines scaling law (Bopt ∝ D^0.383) gives:

- For depth=6 with 10.5 ratio: **auto batch size ≈ 262,144 tokens**
- At seq_len=512: `device_batch_size=32` → 16,384 tokens/fwd → 16 gradient accumulation steps
- At seq_len=2048: `device_batch_size=32` → 65,536 tokens/fwd → 4 gradient accumulation steps

If auto-compute produces batch sizes too large for reasonable gradient accumulation, we can override with `--total-batch-size=65536` or `--total-batch-size=131072`.

## Cost Estimate

| Stage | GPU | Est. Time | Est. Cost |
|-------|-----|-----------|-----------|
| Stage 1 (~929 iters, seq_len=512) | A100 | ~5-15 min | $0.25-0.60 |
| Stage 2 (500 iters, seq_len=2048) | A100 | ~10-20 min | $0.40-0.80 |
| Stage 3 (~929 iters, seq_len=2048) | A100 | ~15-30 min | $0.60-1.25 |
| Eval (3 checkpoints × evals) | A100 | ~10-15 min | $0.40-0.60 |
| **Total** | **A100** | **~40-80 min** | **$1.65-3.25** |

These estimates are rough — actual throughput depends on batch size, gradient accumulation, and whether evals run between stages. P3's total cost should be well under $10 even with failed runs and reruns.

## Param Count Reference Table

Verified by instantiating `GPT` on meta device (see Phase 2 + step 3.2.1):

| Depth | Dim | Heads | Total Params | Scaling Params |
|-------|-----|-------|-------------|----------------|
| 4 | 256 | 2 | 36,700,296 | 11,534,464 |
| **6** | **384** | **3** | **73,531,692** | **23,200,032** |
| 8 | 512 | 4 | 125,829,648 | 41,943,552 |
| 12 | 768 | 6 | 286,262,424 | 110,101,632 |

Note: Total params are inflated by value embeddings (~51% of total for d6). Scaling laws use `scaling_params` (transformer matrices + lm_head) which better predict loss.
