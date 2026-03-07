# Running, Monitoring & Troubleshooting

## 1. Running

```bash
modal run --detach a3/shared/scripts/main.py --config a3/<part>/configs/<name>.yaml
```

| Flag | What it does |
|------|-------------|
| `--detach` | Pipeline runs entirely on Modal. Survives laptop close, Wi-Fi drops, terminal exit. |
| (without `--detach`) | Output streams to your terminal. Pipeline dies if you disconnect. |

Always use `--detach` for real runs.

## 2. Monitoring

### 2.1 Modal dashboard

1. Go to [modal.com](https://modal.com) → your workspace → **Apps** → `a3-nanochat`
2. Shows running / completed / failed function calls
3. Click a function call → **Logs** tab for live output
4. Pipeline prints `[train]` and `[eval]` prefixed lines so you can follow progress

### 2.2 W&B

1. Go to [wandb.ai](https://wandb.ai) → project `490-autobook-a3`
2. Find your run by the `run` name from your YAML config
3. **Charts**: `train/loss`, `val/bpb` over steps
4. **Config** tab: shows all training args + `git_hash` for reproducibility

## 3. Results

### 3.1 Where results land

All results are stored on your Modal Volume (`a3-checkpoints`):

| What | Path on Volume |
|------|---------------|
| Checkpoints | `base_checkpoints/<model_tag>/model_<step>.pt` |
| CORE CSVs | `base_eval/<model_tag>_<step>.csv` |
| Custom eval JSONs | `custom_evals/<model_tag>_<step>.json` |

### 3.2 Browse files on the Volume

```bash
modal volume ls a3-checkpoints base_checkpoints/
modal volume ls a3-checkpoints base_checkpoints/<model_tag>/
modal volume ls a3-checkpoints base_eval/
modal volume ls a3-checkpoints custom_evals/
```

### 3.3 Download files

```bash
modal volume get a3-checkpoints base_eval/<file> ./a3/<part>/results/
modal volume get a3-checkpoints custom_evals/<file> ./a3/<part>/results/
```

### 3.4 W&B export

1. Go to the project page → **Table** view → **Export CSV**
2. Save to `a3/<part>/results/`

### 3.5 Commit to repo

```bash
git add a3/<part>/results/
git commit -m "<part>: add eval results"
```

## 4. Troubleshooting

### 4.1 OOM

- **Symptom**: `CUDA out of memory` in Modal logs
- **Fix**: halve `device_batch_size` in your YAML (e.g., 128 → 64 → 32), rerun

### 4.2 Secret not found

- **Symptom**: `Secret 'wandb-secret' not found`
- **Fix**: run `modal secret list` — check the secret exists and the name is exactly `wandb-secret`

### 4.3 Checkpoint not found

- **Symptom**: `No checkpoints found in ...`
- **Fix**: run `modal volume ls a3-checkpoints base_checkpoints/` — check that `model_tag` in your eval config matches a directory that exists
- For eval-only configs with explicit `step:`, verify that step number exists: `modal volume ls a3-checkpoints base_checkpoints/<model_tag>/`

### 4.4 Git ref not found

- **Symptom**: `error: pathspec '<ref>' did not match any file(s) known to git`
- **Fix**: push your branch to the nanochat fork first, then verify it appears on GitHub before rerunning

### 4.5 Timeout

- **Symptom**: run killed mid-training, Modal dashboard shows timeout
- **Fix**: increase `timeout_hours` in your YAML config, rerun
