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
| P3 | Context window extension (2 stages + eval) | A10G | $2–10 |
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
