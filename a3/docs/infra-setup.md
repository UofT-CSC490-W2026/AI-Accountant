# A3: Pre-training Nanochat

## Infrastructure

### Why Modal

Modal provides the simplest path for single-GPU small model training:

- **Per-second billing** — no minimum commitment, pay only for what you use
- **Zero infra setup** — no SSH keys, no cluster management, no CUDA installs
- **Built-in Volumes** — persistent disk for checkpoints that survives across runs
- **Image caching** — container rebuilds only when dependencies change

### GPU Pricing

| GPU | VRAM | $/hr | BF16 Support | Use Case |
|-----|------|------|-------------|----------|
| T4 | 16 GB | $0.59 | No (FP16 only) | Not recommended for nanochat |
| A10G | 24 GB | $1.10 | Yes | P2 ablations, P3 context extension |
| A100-80GB | 80 GB | $2.50 | Yes | P4 full nanochat |
| H100 | 80 GB | $3.95 | Yes | P4 if faster turnaround needed |

**Note**: A10G is the minimum for nanochat — it requires BF16 (same exponent range as FP32, no loss scaling needed, half memory). T4 only supports FP16, which requires loss scaling.

### Modal Concepts

- **Volume**: Persistent disk mounted into containers. Used for checkpoint storage. Survives across runs — no re-downloading checkpoints on restart.
- **Image**: Container definition with dependencies (PyTorch, wandb, nanochat). Cached after first build.
- **Secret**: Environment variables injected at runtime. Used for `WANDB_API_KEY`.

### Cost Estimates

| Part | Description | GPU | Est. Cost |
|------|-------------|-----|-----------|
| P2 | Picochat ablations (4 runs) | A10G | $2–20 |
| P3 | Context window extension (2 stages + eval) | A100 | $1–5 |
| P4 | Full nanochat training | A100 | $30–100 |

### Available Credits

- **Modal**: $500 (primary compute)
- **Anyscale**: $1,000 (backup for P4 if A100 availability is limited)
- **AWS**: backup

## Global Config

### Compute Platform

All training runs use **Modal**. See [Infrastructure](#infrastructure) for GPU pricing and credits.

### Weights & Biases

- **Project**: `490-autobook-a3`
- **Tag convention**: each run is tagged by part (`p2`, `p3`, `p4`) so runs from all parts coexist in one project
- **Commit hash**: every run logs the nanochat git commit hash in W&B config (`git_hash` field) for reproducibility

### Nanochat Fork

- **URL**: https://github.com/seonghyunban/nanochat
- **Branch strategy**:
  - `master` — baseline code (frozen, do not push)
  - `baseline-v0` — immutable tag on `master`, used as the reference point for all baseline runs
  - `p2` — P2 teammate's architecture changes (branched from `master`)
- **Config field**: YAML configs use `nanochat_ref` to specify which branch or tag to check out (e.g., `baseline-v0`, `p2`)
- **Runtime fetch**: Modal runner does `git fetch origin --tags` before checkout so a single cached image serves all refs

## Nanochat Architecture

Reference for the nanochat codebase. All facts verified against source (commit `baseline-v0`).

### The `--depth` Dial

Nanochat uses a single `--depth` parameter to control model size:

```
model_dim = depth * aspect_ratio          # aspect_ratio defaults to 64
num_heads = model_dim / head_dim          # head_dim defaults to 128
```

Example: `--depth=6` → `model_dim=384`, `num_heads=3` (picochat-sized).

### GPTConfig

| Field | Default | Description |
|-------|---------|-------------|
| `sequence_len` | 2048 | Max context length |
| `vocab_size` | 32768 | Tokenizer vocabulary size |
| `n_layer` | 12 | Number of transformer blocks (= depth) |
| `n_head` | 6 | Query heads |
| `n_kv_head` | 6 | Key/value heads (GQA) |
| `n_embd` | 768 | Model dimension |
| `window_pattern` | "SSSL" | Sliding window attention pattern |

### RoPE (Rotary Position Embeddings)

Nanochat uses RoPE for positional encoding — a fixed mathematical formula that computes each token's position at runtime from sinusoidal frequencies. Nothing about position is learned or stored in the checkpoint:

```python
self.register_buffer("cos", cos, persistent=False)  # NOT saved to checkpoint
self.register_buffer("sin", sin, persistent=False)
```

This is why changing `--max-seq-len` on resume works: no positional embedding weights to mismatch. The RoPE cache is recomputed at model init from the current config.

The cache is pre-computed at 10x the training sequence length, so inference can handle sequences up to 10x training length without error.

### Key CLI Args (`base_train.py`)

| Flag | Default | Description |
|------|---------|-------------|
| `--depth` | 20 | Transformer depth |
| `--max-seq-len` | 2048 | Context length |
| `--num-iterations` | -1 | Total optimization steps (not additional on resume) |
| `--resume-from-step` | -1 | Resume from this checkpoint step |
| `--model-tag` | None | Override checkpoint directory name (default: `d{depth}`) |
| `--save-every` | -1 | Checkpoint interval (-1 = only at end) |
| `--run` | "dummy" | W&B run name ("dummy" disables logging) |
| `--device-batch-size` | 32 | Per-device batch size |
| `--total-batch-size` | -1 | Total batch size in tokens (-1 = auto-compute) |
| `--window-pattern` | "SSSL" | Sliding window pattern (L=full, S=half context) |

### Checkpoint Format

Checkpoints are stored at `{base_dir}/base_checkpoints/{model_tag}/`:

| File | Contents |
|------|----------|
| `model_{step:06d}.pt` | Model weights (state_dict) |
| `optim_{step:06d}_rank{rank}.pt` | Optimizer state (sharded per rank) |
| `meta_{step:06d}.json` | Metadata: step, val_bpb, model_config, user_config, dataloader state |

**Storage path**: `~/.cache/nanochat/` by default. Override with `NANOCHAT_BASE_DIR` env var. On Modal, set `NANOCHAT_BASE_DIR=/checkpoints` and mount a Volume there.

### Resume Behavior

On resume (`--resume-from-step=N`):

- Model weights loaded from checkpoint, overwriting freshly initialized weights
- Optimizer state restored (including momentum)
- Dataloader state restored (resumes from same position in dataset)
- `step` variable set to N, training continues until `--num-iterations` (total)
- Current CLI args are used for model config — **not** the checkpoint's saved config
- This means `--max-seq-len` can change on resume (RoPE recomputes, dataloader uses new length)

**What can change on resume**: `--max-seq-len`, `--num-iterations`, `--save-every`, `--eval-every`, `--run`
**What should NOT change**: `--depth`, `--head-dim`, `--aspect-ratio` (would cause shape mismatch in `load_state_dict`)

### Model Loading API

For evaluation scripts:

```python
from nanochat.checkpoint_manager import load_model

model, tokenizer, meta_data = load_model(
    "base",           # source: "base", "sft", or "rl"
    device,           # torch.device
    phase="eval",     # "eval" or "train"
    model_tag="pico-short",  # checkpoint directory name
    step=1000,        # checkpoint step (None = latest)
)
```

Returns model in eval mode, ready for inference. Uses `NANOCHAT_BASE_DIR` for path resolution.

### Eval System

**Built-in evals** (`python -m scripts.base_eval`):
- `--eval bpb` — bits per byte on train/val splits
- `--eval core` — CORE benchmark (ICL tasks: MMLU, ARC, etc.)
- `--eval sample` — generate text samples

**Custom evals**: No plugin system. Write a standalone script that imports `load_model()` and implements custom evaluation logic. The `core_eval.forward_model()` function provides a useful primitive: takes `BxT` tokens, returns `BxT` losses and predictions.

### CPU/MPS Testing Mode

For local testing without a GPU:

```bash
python -m scripts.base_train --depth=6 --head-dim=64 --window-pattern=L \
    --max-seq-len=512 --device-batch-size=1 --eval-tokens=512 \
    --core-metric-every=-1 --total-batch-size=512 --num-iterations=20
```

Note: `--window-pattern=L` is required on CPU/MPS because SDPA fallback doesn't support sliding window attention. `--head-dim=64` is needed because small models with default `--head-dim=128` may have `model_dim < head_dim`.
