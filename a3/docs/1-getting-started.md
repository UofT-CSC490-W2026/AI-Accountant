# Getting Started

## 1. Prerequisites

You need three accounts before starting:

- **GitHub** — you already have this
- **Modal** ([modal.com](https://modal.com)) — GPU compute platform
- **Weights & Biases** ([wandb.ai](https://wandb.ai)) — experiment tracking

## 2. Setup

### 2.1 Modal

```bash
pip install modal
modal token new          # opens browser, authenticates your account
```

Create a secret so Modal can log to W&B on your behalf:

```bash
modal secret create wandb-secret WANDB_API_KEY=<paste-your-key-here>
```

Verify it exists:

```bash
modal secret list        # should show wandb-secret in the list
```

### 2.2 Weights & Biases

```bash
pip install wandb
```

- Send your W&B username to a teammate so they can add you to the project
- **Project name**: `490-autobook-a3` — all parts (P2, P3, P4) share this project
- **Find your API key**: [wandb.ai/authorize](https://wandb.ai/authorize) — copy it for the Modal secret above

### 2.3 Repository

```bash
git clone <AI-Accountant repo URL>
cd AI-Accountant
git checkout a3
```

Verify the pipeline scripts exist:

```bash
ls a3/shared/scripts/main.py    # should exist
```

## 3. How the Pipeline Works

```
YAML config ──► main.py ──► Modal cloud
                               │
                          ┌────┴────┐
                          │  setup  │  (downloads tokenizer + data)
                          └────┬────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                 stage 1    stage 2    stage 3    (GPU containers, parallel if independent)
                    │          │          │
                    ▼          ▼          ▼
                 eval 1     eval 2     eval 3     (GPU containers, all parallel)
                    │          │          │
                    ▼          ▼          ▼
              Modal Volume (checkpoints, CSVs, JSONs)
                    +
              W&B (training curves, configs)
```

1. You write a YAML config describing training stages and evals
2. `main.py` reads the YAML and sends the work to Modal
3. Modal spins up GPU containers and runs nanochat training
4. After training, Modal runs evals on each checkpoint
5. Results land in two places: training curves go to W&B, eval files go to your Modal Volume

## 4. Nanochat Fork

All training runs use a shared fork of nanochat.

- **Fork URL**: [github.com/seonghyunban/nanochat](https://github.com/seonghyunban/nanochat)

**If you modify nanochat code** (P2 architecture changes):

1. Create a branch on the fork (e.g., `p2-change1`)
2. Push your changes to the fork
3. Set `nanochat_ref: p2-change1` in your YAML config

**If you don't modify nanochat code**:

- Use `nanochat_ref: baseline-v0` (immutable tag on vanilla nanochat)

**Important**: Modal runs `git fetch` + `checkout` on the remote fork — it does not see your local changes. Push your branch to the fork first, then run. Forgetting to push means Modal runs old code with no error message.
