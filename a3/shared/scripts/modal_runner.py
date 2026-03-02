"""Modal runner for A3 nanochat training and evaluation.

Reads a YAML config, resolves stage dependencies, and dispatches
training + eval jobs on Modal GPUs.

Independent stages and evals run in parallel via .starmap().
"""

import re

import modal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WANDB_PROJECT = "490-autobook-a3"
NANOCHAT_DIR = "/root/nanochat"
VOLUME_PATH = "/data/checkpoints"
CKPT_SUBDIR = "base_checkpoints"
EVAL_SUBDIR = "base_eval"
CKPT_STEP_RE = re.compile(r"model_(\d+)\.pt$")

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

wandb_secret = modal.Secret.from_name("wandb-secret")


# ---------------------------------------------------------------------------
# Helpers (used inside Modal containers)
# ---------------------------------------------------------------------------

def _checkout_ref(ref: str):
    """Fetch latest refs and checkout target. Used inside Modal containers."""
    import subprocess

    subprocess.run(["git", "fetch", "origin", "--tags"], check=True)
    subprocess.run(["git", "checkout", ref], check=True)


def _parse_eval_stdout(stdout: str) -> dict:
    """Extract BPB and CORE metrics from base_eval stdout."""
    results = {}
    for line in stdout.splitlines():
        if "train bpb:" in line:
            results["train_bpb"] = float(line.split(":")[-1].strip())
        elif "val bpb:" in line:
            results["val_bpb"] = float(line.split(":")[-1].strip())
        elif "CORE metric:" in line:
            results["core_metric"] = float(line.split(":")[-1].strip())

    for expected in ("train_bpb", "val_bpb", "core_metric"):
        if expected not in results:
            print(f"[eval] WARNING: '{expected}' not found in base_eval output")

    return results


def _parse_core_csv(csv_path: str) -> dict:
    """Parse per-task CORE results from nanochat's CSV output."""
    import csv
    import os

    if not os.path.exists(csv_path):
        return {}

    tasks = {}
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header row
        for row in reader:
            if len(row) >= 3:
                try:
                    tasks[row[0].strip()] = {
                        "accuracy": float(row[1].strip()),
                        "centered": float(row[2].strip()),
                    }
                except ValueError:
                    pass
    return tasks


# ---------------------------------------------------------------------------
# Setup (one-time): download tokenizer + data shards
# ---------------------------------------------------------------------------

HF_TOKENIZER_BASE = "https://huggingface.co/sdobson/nanochat/resolve/main"
TOKENIZER_FILES = ["tokenizer.pkl", "token_bytes.pt"]


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=3600,  # no GPU needed — downloads only
)
def setup(nanochat_ref: str):
    """Download pre-trained tokenizer and data shards. Idempotent — skips if already done."""
    import os
    import subprocess
    import urllib.request

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)
    _checkout_ref(nanochat_ref)

    tokenizer_dir = os.path.join(VOLUME_PATH, "tokenizer")
    all_exist = all(
        os.path.exists(os.path.join(tokenizer_dir, f)) for f in TOKENIZER_FILES
    )
    if all_exist:
        print("[setup] Tokenizer already exists, skipping.")
    else:
        os.makedirs(tokenizer_dir, exist_ok=True)
        for fname in TOKENIZER_FILES:
            url = f"{HF_TOKENIZER_BASE}/{fname}"
            dest = os.path.join(tokenizer_dir, fname)
            print(f"[setup] Downloading {fname}...")
            urllib.request.urlretrieve(url, dest)
        print("[setup] Tokenizer downloaded.")

    # Download data shards (needed for training, idempotent)
    print("[setup] Ensuring data shards exist...")
    subprocess.run(["python", "-m", "nanochat.dataset", "-n", "8"], check=True)

    volume.commit()
    print("[setup] Done.")


# ---------------------------------------------------------------------------
# Train function
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100",        # change here to switch GPU for all training stages
    timeout=3 * 3600,  # 3 hours max
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
    os.environ["WANDB_PROJECT"] = WANDB_PROJECT
    os.chdir(NANOCHAT_DIR)

    _checkout_ref(nanochat_ref)

    # Record commit hash
    git_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"[train] nanochat commit: {git_hash}")

    # Build CLI command: convert underscore keys to kebab-case flags
    cmd = ["python", "-m", "scripts.base_train"]
    for key, value in args.items():
        cli_key = key.replace("_", "-")
        cmd.append(f"--{cli_key}={value}")

    print(f"[train] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Determine final step from checkpoint files
    model_tag = args.get("model_tag", f"d{args['depth']}")
    checkpoint_dir = os.path.join(VOLUME_PATH, CKPT_SUBDIR, model_tag)
    checkpoint_files = glob.glob(os.path.join(checkpoint_dir, "model_*.pt"))
    if not checkpoint_files:
        raise FileNotFoundError(f"No checkpoints found in {checkpoint_dir}")

    steps = []
    for f in checkpoint_files:
        m = CKPT_STEP_RE.search(os.path.basename(f))
        if m:
            steps.append(int(m.group(1)))
    if not steps:
        raise FileNotFoundError(f"No valid checkpoint files in {checkpoint_dir}")
    final_step = max(steps)
    print(f"[train] Final step: {final_step}")

    # Log git hash to W&B run (best-effort — don't fail training on W&B issues)
    run_name = args.get("run")
    if run_name and run_name != "dummy":
        try:
            import wandb

            api = wandb.Api()
            runs = api.runs(WANDB_PROJECT, filters={"display_name": run_name})
            if runs:
                runs[0].config["git_hash"] = git_hash
                runs[0].update()
                print(f"[train] Logged git_hash to W&B run: {run_name}")
        except Exception as e:
            # Intentionally broad: W&B logging is non-critical auxiliary work
            print(f"[train] WARNING: could not update W&B with git hash: {e}")

    volume.commit()

    return {
        "model_tag": model_tag,
        "final_step": final_step,
        "git_hash": git_hash,
    }


# ---------------------------------------------------------------------------
# Eval function
# ---------------------------------------------------------------------------

eval_image = image.add_local_dir("a3/p3/evals", remote_path="/root/evals")

@app.function(
    image=eval_image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100",      # change here to switch GPU for all eval stages
    timeout=3600,    # 1 hour max
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
        custom_eval_script: Basename of a script mounted at /root/evals/,
            or None. The script must expose run_eval(checkpoint_dir, model_tag,
            step) -> dict.

    Returns:
        Dict with train_bpb, val_bpb, core_metric, core_tasks, and
        optionally custom_eval results.
    """
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)

    _checkout_ref(nanochat_ref)

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

    results.update(_parse_eval_stdout(proc.stdout))

    # nanochat writes CORE CSV as base_model_{step}.csv without model_tag in filename.
    # Each eval container writes locally; reads happen before volume.commit(), so
    # parallel evals with the same step number don't collide.
    model_slug = f"base_model_{step:06d}"
    csv_path = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"{model_slug}.csv")
    core_tasks = _parse_core_csv(csv_path)
    if core_tasks:
        results["core_tasks"] = core_tasks

    # --- Custom eval (direct import, no subprocess) ---
    if custom_eval_script:
        import sys

        sys.path.insert(0, "/root/evals")
        from context_length_eval import run_eval

        print("[eval] Running custom: context_length_eval.run_eval()")
        results["custom_eval"] = run_eval(
            checkpoint_dir=VOLUME_PATH,
            model_tag=checkpoint_tag,
            step=step,
        )

    volume.commit()
    return results


# ---------------------------------------------------------------------------
# Orchestrator (runs remotely on Modal — immune to local disconnects)
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    timeout=4 * 3600,  # 4 hours max for full pipeline
)
def run_pipeline(cfg: dict) -> dict:
    """Run the full training + eval pipeline remotely.

    Dispatches setup, training stages, and evals. Returns all results.
    Runs on Modal (no GPU) so the pipeline survives local client disconnects.
    """
    nanochat_ref = cfg["nanochat_ref"]
    experiment_name = cfg.get("experiment_name", "experiment")

    print(f"\n{'='*60}")
    print(f"  {experiment_name}")
    print(f"  nanochat ref: {nanochat_ref}")
    print(f"{'='*60}")

    # --- Setup (idempotent) ---
    print("\n[pipeline] Ensuring tokenizer exists on volume...")
    setup.remote(nanochat_ref)

    # --- Training stages ---
    stage_results = {}  # stage_name -> train result dict

    # Wave 1: independent stages (no depends_on) — run in parallel
    independent = [s for s in cfg["stages"] if "depends_on" not in s]
    if independent:
        names = [s["name"] for s in independent]
        inputs = [(nanochat_ref, dict(s["args"])) for s in independent]
        print(f"\n[pipeline] Running {len(independent)} independent stages in parallel: {names}")
        for stage, result in zip(independent, train.starmap(inputs)):
            stage_results[stage["name"]] = result
            print(f"[pipeline] [{stage['name']}] Done: final_step={result['final_step']}")

    # Wave 2: dependent stages (sequential — each resolves from prior results)
    for stage in cfg["stages"]:
        if "depends_on" not in stage:
            continue  # already ran in wave 1

        stage_name = stage["name"]
        dep_name = stage["depends_on"]
        if dep_name not in stage_results:
            raise ValueError(
                f"Stage '{stage_name}' depends on '{dep_name}', "
                f"which hasn't run yet. Check stage ordering in config."
            )

        args = dict(stage["args"])
        dep_final_step = stage_results[dep_name]["final_step"]
        args["resume_from_step"] = dep_final_step
        args["num_iterations"] = dep_final_step + stage["extra_iterations"]

        print(f"\n[pipeline] [{stage_name}] Resuming from '{dep_name}' step {dep_final_step}")
        print(f"[pipeline] [{stage_name}] num_iterations={args['num_iterations']}")
        print(f"[pipeline] [{stage_name}] Starting training...")

        result = train.remote(nanochat_ref, args)
        stage_results[stage_name] = result
        print(f"[pipeline] [{stage_name}] Done: final_step={result['final_step']}")

    # --- Evaluation (all evals in parallel) ---
    eval_entries = cfg.get("eval", [])
    eval_inputs = []

    for eval_entry in eval_entries:
        checkpoint = eval_entry["checkpoint"]

        after_stage = eval_entry.get("after_stage")
        if after_stage:
            if after_stage not in stage_results:
                raise ValueError(
                    f"Eval after_stage '{after_stage}' not found in stage results"
                )
            step = stage_results[after_stage]["final_step"]
        else:
            step = eval_entry["step"]

        evals = eval_entry.get("evals", [])
        custom_script = eval_entry.get("custom_eval") if "custom" in evals else None

        eval_inputs.append((nanochat_ref, checkpoint, step, custom_script))
        print(f"[pipeline] [eval] Queued: {checkpoint} @ step {step}")

    eval_results = []
    if eval_inputs:
        print(f"\n[pipeline] Running {len(eval_inputs)} evals in parallel...")
        eval_results = list(evaluate.starmap(eval_inputs))

        for result in eval_results:
            tag = result.get("checkpoint_tag", "?")
            s = result.get("step", "?")
            val_bpb = result.get("val_bpb", "N/A")
            core = result.get("core_metric", "N/A")
            print(f"[pipeline]   {tag}@{s}: BPB={val_bpb}, CORE={core}")
            if "custom_eval" in result:
                ppl = result["custom_eval"].get("aggregate_perplexity")
                print(f"[pipeline]   Positional PPL: {ppl:.2f}" if ppl else "[pipeline]   Positional PPL: N/A")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  SUMMARY: {experiment_name}")
    print(f"{'='*60}")
    for name, res in stage_results.items():
        print(f"  {name}: final_step={res['final_step']}")
    for i, res in enumerate(eval_results):
        tag = res.get("checkpoint_tag", "?")
        s = res.get("step", "?")
        bpb = res.get("val_bpb", "N/A")
        core = res.get("core_metric", "N/A")
        print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")

    return {
        "experiment_name": experiment_name,
        "stage_results": stage_results,
        "eval_results": eval_results,
    }


# ---------------------------------------------------------------------------
# Local entrypoint (thin wrapper — just parses YAML and dispatches)
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(config: str):
    """Launch the pipeline from a YAML config.

    Usage:
        modal run a3/shared/scripts/modal_runner.py --config a3/p3/configs/p3_baseline.yaml

    With --detach, the pipeline runs entirely on Modal (survives local disconnects):
        modal run --detach a3/shared/scripts/modal_runner.py --config ...
    """
    import yaml

    with open(config) as f:
        cfg = yaml.safe_load(f)

    experiment_name = cfg.get("experiment_name", "experiment")
    print(f"Launching pipeline: {experiment_name}")
    print("Tip: use 'modal run --detach ...' to survive local disconnects.\n")

    results = run_pipeline.remote(cfg)

    # Print summary locally (only reached if not using --detach)
    print(f"\n{'='*60}")
    print(f"  RESULTS: {experiment_name}")
    print(f"{'='*60}")
    for name, res in results["stage_results"].items():
        print(f"  {name}: final_step={res['final_step']}")
    for i, res in enumerate(results["eval_results"]):
        tag = res.get("checkpoint_tag", "?")
        s = res.get("step", "?")
        bpb = res.get("val_bpb", "N/A")
        core = res.get("core_metric", "N/A")
        print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")
