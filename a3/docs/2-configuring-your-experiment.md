# Configuring Your Experiment

## 1. YAML Structure

A minimal config with one training stage and one eval:

```yaml
experiment_name: p2-baseline       # W&B group name
nanochat_ref: main                 # branch or tag on the nanochat fork
gpu: A100-80GB                     # Modal GPU type
timeout_hours: 3                   # max wall time per stage

train:
  - name: train
    args:
      depth: 6                     # model depth
      max_seq_len: 512             # context length
      model_tag: pico-baseline     # checkpoint folder name — pick something unique
      run: p2-baseline             # W&B run name — pick something unique

eval:
  - checkpoint: pico-baseline      # must match model_tag above
    after_stage: train             # eval the checkpoint from this stage
    evals: [bpb, core]            # which evals to run
```

### Top-level fields

| Field | What it does |
|-------|-------------|
| `experiment_name` | Any string. Becomes the W&B group name and appears in logs. |
| `nanochat_ref` | Branch or tag on the nanochat fork. Use `baseline-v0` for unmodified nanochat. |
| `gpu` | Modal GPU type: `A100-80GB`, `A10G`, `H100`. |
| `timeout_hours` | Max wall time per training/eval stage. Increase for large models. Default: 3. |

## 2. Training Stages

### 2.1 Stage fields

Each stage in the `train:` list has:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Any string. Used in logs and eval `after_stage` references. |
| `args` | Yes | Dict of nanochat CLI arguments (see 2.2). |

### 2.2 args reference

| Key | Default | Description |
|-----|---------|-------------|
| `depth` | 20 | Model depth. 6 = picochat, 20 = full nanochat. |
| `max_seq_len` | 2048 | Context length in tokens. |
| `model_tag` | `d{depth}` | Checkpoint folder name. Pick something unique per experiment. |
| `device_batch_size` | 32 | Sequences per forward pass (see 2.4). |
| `num_iterations` | auto | Total training steps. Omit to let nanochat auto-compute from scaling law. |
| `save_every` | -1 | Checkpoint interval in steps. -1 = save only at end. |
| `eval_every` | -1 | Val BPB eval interval during training. |
| `log_every` | -1 | W&B logging interval. |
| `core_metric_every` | -1 | -1 to disable CORE during training (run post-hoc instead). |
| `sample_every` | -1 | -1 to disable text sampling during training. |
| `run` | `"dummy"` | W&B run name. `"dummy"` disables W&B logging. Pick something unique. |
| `script` | `scripts.base_train` | Training script module. Only change if using a different script. |

### 2.3 args to CLI mapping

YAML keys use underscores. The runner converts them to kebab-case CLI flags:

```
max_seq_len: 512       →  --max-seq-len=512
device_batch_size: 128 →  --device-batch-size=128
model_tag: pico-test   →  --model-tag=pico-test
```

Values are passed as-is.

### 2.4 device_batch_size guidance

| Depth | seq_len | device_batch_size | Note |
|-------|---------|-------------------|------|
| 6 | 512 | 512 | Fits in one forward pass on A100-80GB |
| 6 | 2048 | 128 | Fits in one forward pass on A100-80GB |
| 20 | 512 | 32 | Reduce to 16 if OOM |
| 20 | 2048 | 32 | Reduce to 16 if OOM |

If you get OOM errors: halve it (128 → 64 → 32). This does not change training dynamics — it only affects how many gradient accumulation steps are used.

### 2.5 Advanced: depends_on + extra_iterations

Only needed if you are resuming training from a previous stage (e.g., context extension). P2 and P4 probably don't need this.

```yaml
train:
  - name: short-context
    args:
      depth: 6
      max_seq_len: 512
      model_tag: pico-short

  - name: extended-context
    depends_on: short-context       # resume from this stage's final checkpoint
    extra_iterations: 500           # train 500 more steps beyond the prior stage
    args:
      depth: 6
      max_seq_len: 2048
      model_tag: pico-short         # same tag — checkpoints coexist by step number
```

The runner auto-computes `resume_from_step` and `num_iterations` from the prior stage's results.

## 3. Evaluation

### 3.1 Built-in evals

```yaml
eval:
  - checkpoint: pico-baseline      # must match model_tag from a stage
    after_stage: train             # auto-resolve step from this stage's final checkpoint
    evals: [bpb, core]            # which evals to run
```

| Eval | What it does |
|------|-------------|
| `bpb` | Bits per byte on train and val splits. |
| `core` | 22-task benchmark (HellaSwag, ARC, PIQA, BoolQ, etc.). |

**Step resolution**: Use `after_stage: <stage-name>` to auto-resolve the checkpoint step from that stage. Alternatively, use `step: <number>` for an explicit step.

### 3.2 When to skip CORE

If the model was trained at `seq_len` shorter than 2048, some CORE prompts may exceed the RoPE cache length and crash. For short-context checkpoints, use `evals: [bpb]` only.

### 3.3 Custom eval

Write a Python file with a `run_eval` function:

```python
def run_eval(checkpoint_dir: str, model_tag: str, step: int) -> dict:
    """Return a dict of results. Saved as JSON on the Volume."""
    # Load model, run eval, return results
    return {"score": 0.42}
```

Place your script at `a3/<part>/evals/<name>.py` and reference it in the YAML:

```yaml
eval:
  - checkpoint: pico-baseline
    after_stage: train
    evals: [bpb, core, custom]                    # include "custom" in the list
    custom_eval: <part>/evals/<name>.py            # path to your script
```

The return value is automatically saved as JSON on the Modal Volume.

## 4. Where to Put Your Config

```
a3/<part>/configs/<name>.yaml
```

Convention: `p2_baseline.yaml`, `p2_ablation1.yaml`, `p4_final.yaml`, etc.

See `a3/p2/configs/p2_template.yaml` and `a3/p4/configs/p4_template.yaml` for ready-to-use starting points.
