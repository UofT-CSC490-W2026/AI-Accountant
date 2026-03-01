# P2 → P3 Interface

## Nanochat Fork

- **Fork URL**: https://github.com/seonghyunban/nanochat
- **Baseline tag**: `baseline-v0` on `master` — frozen, immutable reference to vanilla nanochat
- **P2 branch**: `p2` — push your architecture changes here, never to `master`
- Clone: `git clone https://github.com/seonghyunban/nanochat.git`
- Switch to your branch: `git checkout p2`

## What P3 Accepts from P2

### Required

- **Picochat depth** (int) — the `--depth` value used for P2 ablations

### Optional

- **Checkpoint** — model_tag + step number, if P2 wants P3 to resume from a P2-trained checkpoint
- **Nanochat branch** — defaults to `p2`; specify if using a different branch name

## What P2 Should Know About P3

- P3 trains picochat at **reduced sequence length** (e.g., 512), then resumes training with sequence length extended to **2048**
- P3 needs picochat to be trainable at both sequence lengths — architecture changes must not break this
- Sequence length change on resume works because nanochat uses **RoPE** (Rotary Position Embeddings), which computes positional encodings at runtime — no stored positional weights to mismatch
- **Critical constraint**: architecture changes must not break `--max-seq-len` change on resume. If your changes introduce any positional component that gets saved in the checkpoint, P3's context extension may fail

## Timeline

- P3 can run independently using the baseline (`baseline-v0`) without waiting for P2
- If P2 delivers a stable config before the deadline, P3 will also run context extension on P2's model (Phase 7) and compare results
