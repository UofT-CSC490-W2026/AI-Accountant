# P2 Training Troubleshooting Log

This file records all issues encountered while setting up and running P2 ablations, with fixes that worked.

## Current expected setup

- `AI-Accountant` branch: `a3-p2`
- `nanochat` branch: `p2-swiglu-layerscale` (pushed to origin)
- P2 configs under `a3/p2/configs/`
- Eval mode for P2 runs: `bpb` only

---

## Pre-Training Checklist (Run Before Launching Jobs)

- [ ] **Repo/branch sanity**
- [ ] In `AI-Accountant`, on `a3-p2` and up to date (`git pull`).
- [ ] In `nanochat`, on `p2-swiglu-layerscale` and up to date (`git pull`).
- [ ] Any required nanochat fixes are committed + pushed **before** Modal runs.

- [ ] **Modal account/workspace sanity**
- [ ] `modal profile current` is the intended workspace/profile.
- [ ] Billing cap is not hit (if you see `workspace billing cycle spend limit reached`, increase cap first).
- [ ] W&B secret exists: `modal secret list` includes `wandb-secret`.

- [ ] **Modal infra sanity**
- [ ] No stale apps consuming resources unexpectedly: `modal app list`.
- [ ] Optional cleanup before launches: `modal app stop <APP_ID>` for dead/unused runs.

- [ ] **Config sanity (training)**
- [ ] `num_iterations` is explicitly set (for P2 full runs: `1433`).
- [ ] `device_batch_size` is safe (`128` for these P2 runs).
- [ ] `total_batch_size` is set (`262144`) for consistent token budget.
- [ ] `eval_every: -1` to avoid mid-training eval interruption path.
- [ ] If resuming, `resume_from_step` matches latest checkpoint step.
- [ ] If starting fresh, remove `resume_from_step`.

- [ ] **Config sanity (evaluation)**
- [ ] `nanochat_ref` points to branch containing latest eval/model fixes.
- [ ] For smoke checks, run CORE smoke first (small `max_per_task`) before full eval.
- [ ] For full report, use `evals: [bpb, core]` on step `1433`.

- [ ] **Checkpoint sanity**
- [ ] Confirm checkpoints exist before eval/resume:
  `modal volume ls a3-checkpoints base_checkpoints/<model_tag>/`
- [ ] Confirm expected step files exist (`model_XXXXXX.pt`, `meta_XXXXXX.json`, optimizer state).

- [ ] **Launch + monitor**
- [ ] Launch with `--detach`.
- [ ] Monitor with:
  `modal app list`
  `modal app logs <APP_ID> --timestamps`
  `modal billing report --for today -r h --tz local`

- [ ] **Success criteria**
- [ ] Training run ends with `final_step=1433`.
- [ ] Eval run prints final `val bpb` and `CORE metric`.
- [ ] Summary shows non-failed result for each model tag.

---

## 1) Modal could not find `a3/shared/scripts/main.py`

### Error

`FileNotFoundError: ... AI-Accountant\\a3/shared/scripts/main.py`

### Cause

Branch `a3-p2` only had `a3/shared/scripts/.gitkeep`; shared runner files were missing.

### Fix

Bring shared files from `a3-p3` into `a3-p2`:

```powershell
git checkout a3-p2
git checkout a3-p3 -- a3/shared
git add a3/shared
git commit -m "Add shared A3 runners"
git push
```

---

## 2) Modal secret creation failed

### Error

`Each item should be of the form <KEY>=VALUE`

### Cause

Passed only W&B value, not key-value pair.

### Fix

```powershell
modal secret create wandb-secret WANDB_API_KEY=<your_key>
modal secret list
```

---

## 3) Local smoke test failed: missing `rustbpe`

### Error

`ModuleNotFoundError: No module named 'rustbpe'`

### Cause

Wrong Python environment (Conda `base`) was used, not project `.venv`.

### Fix

Use repo environment and explicit interpreter path:

```powershell
uv venv
uv sync --extra gpu
& .\.venv\Scripts\python.exe -c "import torch, rustbpe; print(torch.__version__)"
```

---

## 4) `.venv` had CPU PyTorch (no CUDA)

### Symptoms

- `torch.cuda.is_available() == False`
- `torch` showed `+cpu`

### Fix

Re-sync GPU extra with `uv` and verify:

```powershell
uv sync --extra gpu --verbose
& .\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

Expected: `2.9.1+cu128`, CUDA version present, `True`.

---

## 5) Local training failed: missing tokenizer files

### Error

`FileNotFoundError ... .scratch/tokenizer/tokenizer.pkl`

### Cause

`NANOCHAT_BASE_DIR` pointed to `.scratch`, but tokenizer artifacts were not created there.

### Fix

```powershell
$env:NANOCHAT_BASE_DIR = "$PWD\.scratch"
& .\.venv\Scripts\python.exe -m scripts.tok_train
```

Also ensure dataset shards exist (next issue).

---

## 6) Local training failed: no parquet data

### Error

`AssertionError: No dataset parquet files found, did you run dataset.py?`

### Cause

No shards in `.scratch/base_data`.

### Fix

```powershell
& .\.venv\Scripts\python.exe -m nanochat.dataset -n 2 -w 2
```

Then rerun `tok_train` so tokenizer is trained from non-empty data.

---

## 7) Local training failed: Triton missing (`torch.compile`)

### Error

`torch._inductor.exc.TritonMissing`

### Cause

`torch.compile` path on local Windows/CUDA environment required Triton.

### Fix (local smoke only)

```powershell
$env:TORCH_COMPILE_DISABLE = "1"
```

Then rerun local smoke tests.

---

## 8) P2 Modal run failed: unsupported `--log-every`

### Error

`base_train.py: error: unrecognized arguments: --log-every=20`

### Cause

`baseline-v0` (and branch used remotely) did not support that CLI argument.

### Fix

Removed `log_every` from all P2 YAML configs.

---

## 9) Pipeline failed after training: `KeyError: 'num_iterations'`

### Error

`final_step = args["num_iterations"]` in runner raised `KeyError`.

### Cause

Runner expected explicit `num_iterations`; configs relied on auto-compute.

### Fix

Set explicit `num_iterations: 1433` in all full P2 configs.

---

## 10) CORE eval failed on seq_len=512 checkpoint

### Error

`AssertionError: Sequence length grew beyond the rotary embeddings cache: 5540 > 5120`

### Cause

Some CORE prompts exceeded `10 * sequence_len` cache for 512-length model.

### Fix

Changed P2 evals to BPB-only:

```yaml
evals: [bpb]
```

for all P2 configs.

---

## 11) OOM on A100 for `SwiGLU + LayerScale`

### Error

`torch.OutOfMemoryError: Tried to allocate 32.00 GiB`

### Cause

`device_batch_size: 512` too large for this variant in training.

### Fix

Use:

- `device_batch_size: 128`
- `total_batch_size: 262144`

in all P2 configs (keeps effective batch consistent via grad accumulation).

---

## 12) Modal message: worker preemption

### Message

`Runner interrupted due to worker preemption ... Function will be restarted`

### Meaning

Infrastructure interruption, not model code failure.

### Action

Monitor run. Retry only if repeated preemption prevents completion.

---

## 13) Modal message: timed out waiting for final app logs

### Message

`Timed out waiting for final app logs`

### Meaning

Client log-stream timeout only. App can still complete successfully.

### Action

Confirm state with:

```powershell
modal app list --json
modal app logs <APP_ID> --timestamps
```

---

## Final config decisions for P2

- Eval mode: `bpb` only
- Explicit iterations: `num_iterations: 1433`
- Batch settings:
  - `device_batch_size: 128`
  - `total_batch_size: 262144`
- `window_pattern: L`

---

## Run order

1. `p2_baseline.yaml` (or baseline eval-only if checkpoint already valid)
2. `p2_swiglu.yaml`
3. `p2_layerscale.yaml`
4. `p2_swiglu_layerscale.yaml`

Smoke config:

- `p2_swiglu_layerscale_smoke.yaml`
