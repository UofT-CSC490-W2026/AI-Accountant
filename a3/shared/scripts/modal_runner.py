"""Modal runner for A3 nanochat training and evaluation.

Reads a YAML config, resolves stage dependencies, and dispatches
training + eval jobs on Modal GPUs.
"""

import modal

# ---------------------------------------------------------------------------
# App, Image, Volume, Secret
# ---------------------------------------------------------------------------

app = modal.App("a3-nanochat")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        # PyTorch — CUDA 12.8 wheel
        "torch==2.9.1",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .pip_install(
        # nanochat runtime deps (from pyproject.toml, minus torch)
        "datasets>=4.0.0",
        "psutil>=7.1.0",
        "regex>=2025.9.1",
        "rustbpe>=0.1.0",
        "scipy>=1.15.3",
        "setuptools>=80.9.0",
        "tabulate>=0.9.0",
        "tiktoken>=0.11.0",
        "tokenizers>=0.22.0",
        "transformers>=4.57.3",
        "wandb>=0.21.3",
        "zstandard>=0.25.0",
    )
    .run_commands("git clone https://github.com/seonghyunban/nanochat.git /root/nanochat")
)

volume = modal.Volume.from_name("a3-checkpoints", create_if_missing=True)
VOLUME_PATH = "/data/checkpoints"

wandb_secret = modal.Secret.from_name("wandb-secret")

NANOCHAT_DIR = "/root/nanochat"


# ---------------------------------------------------------------------------
# Setup (one-time): download data + train tokenizer
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    gpu="A100",
    timeout=3600,
)
def setup(nanochat_ref: str):
    """Download data shards and train tokenizer. Idempotent — skips if already done."""
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)

    subprocess.run(["git", "fetch", "origin", "--tags"], check=True)
    subprocess.run(["git", "checkout", nanochat_ref], check=True)

    tokenizer_path = os.path.join(VOLUME_PATH, "tokenizer", "tokenizer.pkl")
    if os.path.exists(tokenizer_path):
        print("[setup] Tokenizer already exists, skipping.")
        return

    print("[setup] Downloading data shards...")
    subprocess.run(["python", "-m", "nanochat.dataset", "-n", "8"], check=True)

    print("[setup] Training tokenizer...")
    subprocess.run(["python", "-m", "scripts.tok_train"], check=True)

    volume.commit()
    print("[setup] Done — tokenizer saved to volume.")


# ---------------------------------------------------------------------------
# Train function
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100",
    timeout=3 * 3600,
)
def train(nanochat_ref: str, args: dict) -> dict:
    """Run nanochat base training for one stage.

    Args:
        nanochat_ref: Git ref (branch or tag) to checkout in the nanochat fork.
        args: Dict mapping nanochat CLI arg names (underscore form) to values.
              e.g. {"depth": 6, "max_seq_len": 512, "model_tag": "pico-short", ...}

    Returns:
        Dict with model_tag, final_step, and git_hash.
    """
    import glob
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.environ["WANDB_PROJECT"] = "490-autobook-a3"
    os.chdir(NANOCHAT_DIR)

    # Fetch latest refs (critical — cached image may be stale)
    subprocess.run(["git", "fetch", "origin", "--tags"], check=True)
    subprocess.run(["git", "checkout", nanochat_ref], check=True)

    # Record commit hash
    git_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"nanochat commit: {git_hash}")

    # Build CLI command: convert underscore keys to kebab-case flags
    cmd = ["python", "-m", "scripts.base_train"]
    for key, value in args.items():
        cli_key = key.replace("_", "-")
        cmd.append(f"--{cli_key}={value}")

    print(f"[train] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Determine final step from checkpoint files
    model_tag = args.get("model_tag", f"d{args['depth']}")
    checkpoint_dir = os.path.join(VOLUME_PATH, "base_checkpoints", model_tag)
    checkpoint_files = glob.glob(os.path.join(checkpoint_dir, "model_*.pt"))
    if not checkpoint_files:
        raise FileNotFoundError(f"No checkpoints found in {checkpoint_dir}")
    final_step = max(
        int(os.path.basename(f).split("_")[-1].split(".")[0])
        for f in checkpoint_files
    )
    print(f"[train] Final step: {final_step}")

    # Log git hash to W&B run
    run_name = args.get("run")
    if run_name and run_name != "dummy":
        try:
            import wandb
            api = wandb.Api()
            runs = api.runs("nanochat", filters={"display_name": run_name})
            if runs:
                runs[0].config["git_hash"] = git_hash
                runs[0].update()
                print(f"[train] Logged git_hash to W&B run: {run_name}")
        except Exception as e:
            print(f"[train] Warning: could not update W&B with git hash: {e}")

    volume.commit()

    return {
        "model_tag": model_tag,
        "final_step": final_step,
        "git_hash": git_hash,
    }


# ---------------------------------------------------------------------------
# Eval function
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100",
    timeout=3600,
    mounts=[modal.Mount.from_local_dir("a3/p3/evals", remote_path="/root/evals")],
)
def evaluate(
    nanochat_ref: str,
    checkpoint_tag: str,
    step: int,
    custom_eval_script: str | None = None,
) -> dict:
    """Run BPB + CORE evals, and optionally a custom eval, on one checkpoint.

    Args:
        nanochat_ref: Git ref (branch or tag) to checkout in the nanochat fork.
        checkpoint_tag: Model tag identifying the checkpoint directory.
        step: Checkpoint step number to evaluate.
        custom_eval_script: Basename of a script mounted at /root/evals/, or None.

    Returns:
        Dict with train_bpb, val_bpb, core_metric, core_tasks, and
        optionally custom_eval results.
    """
    import json
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir("/root/nanochat")

    # Fetch latest code and checkout the target ref
    subprocess.run(["git", "fetch", "origin", "--tags"], check=True)
    subprocess.run(["git", "checkout", nanochat_ref], check=True)

    # Reload volume to see checkpoints written by training containers
    volume.reload()

    results = {"checkpoint_tag": checkpoint_tag, "step": step}

    # --- Standard evals: BPB + CORE ---
    cmd = [
        "python", "-m", "scripts.base_eval",
        "--eval=bpb,core",
        f"--model-tag={checkpoint_tag}",
        f"--step={step}",
    ]
    print(f"[eval] Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        proc.check_returncode()

    # Parse BPB and CORE metric from stdout
    for line in proc.stdout.splitlines():
        if "train bpb:" in line:
            results["train_bpb"] = float(line.split(":")[-1].strip())
        elif "val bpb:" in line:
            results["val_bpb"] = float(line.split(":")[-1].strip())
        elif "CORE metric:" in line:
            results["core_metric"] = float(line.split(":")[-1].strip())

    # Parse per-task CORE results from the CSV written by base_eval
    model_slug = f"base_model_{step:06d}"
    csv_path = os.path.join(VOLUME_PATH, "base_eval", f"{model_slug}.csv")
    if os.path.exists(csv_path):
        core_tasks = {}
        with open(csv_path) as f:
            for line in f:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 3 and parts[0] != "Task":
                    try:
                        core_tasks[parts[0]] = {
                            "accuracy": float(parts[1]),
                            "centered": float(parts[2]),
                        }
                    except ValueError:
                        pass
        results["core_tasks"] = core_tasks

    # --- Custom eval ---
    if custom_eval_script:
        script_name = os.path.basename(custom_eval_script)
        remote_script = f"/root/evals/{script_name}"
        output_path = "/tmp/custom_eval_results.json"

        cmd = [
            "python", remote_script,
            f"--checkpoint-dir={VOLUME_PATH}",
            f"--model-tag={checkpoint_tag}",
            f"--step={step}",
            f"--output={output_path}",
        ]
        print(f"[eval] Running custom: {' '.join(cmd)}")
        env = os.environ.copy()
        env["PYTHONPATH"] = "/root/nanochat"
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
        print(proc.stdout)
        if proc.returncode != 0:
            print(proc.stderr)
            proc.check_returncode()

        with open(output_path) as f:
            results["custom_eval"] = json.load(f)

    volume.commit()
    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(config: str):
    """Run the full training + eval pipeline from a YAML config.

    Usage:
        modal run a3/shared/scripts/modal_runner.py --config a3/p3/configs/p3_baseline.yaml
    """
    import yaml

    with open(config) as f:
        cfg = yaml.safe_load(f)

    nanochat_ref = cfg["nanochat_ref"]
    experiment_name = cfg.get("experiment_name", "experiment")

    print(f"\n{'='*60}")
    print(f"  {experiment_name}")
    print(f"  nanochat ref: {nanochat_ref}")
    print(f"{'='*60}")

    # --- Setup (idempotent) ---
    print("\n[setup] Ensuring tokenizer exists on volume...")
    setup.remote(nanochat_ref)

    # --- Training stages ---
    stage_results = {}  # stage_name -> train result dict

    for stage in cfg["stages"]:
        stage_name = stage["name"]
        args = dict(stage["args"])  # copy to avoid mutating config

        # Resolve dependencies: inject resume_from_step and num_iterations
        if "depends_on" in stage:
            dep_name = stage["depends_on"]
            if dep_name not in stage_results:
                raise ValueError(
                    f"Stage '{stage_name}' depends on '{dep_name}', "
                    f"which hasn't run yet. Check stage ordering in config."
                )
            dep_final_step = stage_results[dep_name]["final_step"]
            args["resume_from_step"] = dep_final_step
            args["num_iterations"] = dep_final_step + stage["extra_iterations"]
            print(f"\n[{stage_name}] Resuming from '{dep_name}' step {dep_final_step}")
            print(f"[{stage_name}] num_iterations={args['num_iterations']}")

        print(f"\n[{stage_name}] Starting training...")
        result = train.remote(nanochat_ref, args)
        stage_results[stage_name] = result
        print(f"[{stage_name}] Done: final_step={result['final_step']}")

    # --- Evaluation ---
    eval_results = []

    for eval_entry in cfg.get("eval", []):
        checkpoint = eval_entry["checkpoint"]

        # Resolve step from after_stage
        after_stage = eval_entry.get("after_stage")
        if after_stage:
            if after_stage not in stage_results:
                raise ValueError(
                    f"Eval after_stage '{after_stage}' not found in stage results"
                )
            step = stage_results[after_stage]["final_step"]
        else:
            step = eval_entry["step"]

        # Pass custom eval script only if "custom" is in the evals list
        evals = eval_entry.get("evals", [])
        custom_script = eval_entry.get("custom_eval") if "custom" in evals else None

        print(f"\n[eval] {checkpoint} @ step {step} (after {after_stage})")
        result = evaluate.remote(nanochat_ref, checkpoint, step, custom_script)
        eval_results.append(result)

        val_bpb = result.get("val_bpb", "N/A")
        core = result.get("core_metric", "N/A")
        print(f"  val BPB: {val_bpb}")
        print(f"  CORE:    {core}")
        if "custom_eval" in result:
            ppl = result["custom_eval"].get("aggregate_perplexity")
            print(f"  Positional PPL: {ppl:.2f}" if ppl else "  Positional PPL: N/A")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {experiment_name}")
    print(f"{'='*60}")
    for name, r in stage_results.items():
        print(f"  {name}: final_step={r['final_step']}")
    for i, r in enumerate(eval_results):
        tag = r.get("checkpoint_tag", "?")
        s = r.get("step", "?")
        bpb = r.get("val_bpb", "N/A")
        core = r.get("core_metric", "N/A")
        print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")
