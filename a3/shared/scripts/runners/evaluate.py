"""Eval function — one checkpoint per GPU. Includes M2 (persist JSON) and M4 (rename CSV)."""

from shared.infra import (
    CUSTOM_EVAL_SUBDIR,
    EVAL_SUBDIR,
    NANOCHAT_DIR,
    VOLUME_PATH,
    app,
    eval_image,
    volume,
    wandb_secret,
)
from shared.helpers import checkout_ref, parse_core_csv, parse_eval_stdout


@app.function(
    image=eval_image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100-80GB",
    timeout=3600,
)
def evaluate(
    nanochat_ref: str,
    checkpoint_tag: str,
    step: int,
    standard_evals: str = "bpb,core",
    custom_eval_script: str | None = None,
) -> dict:
    """Run standard evals and optionally a custom eval on one checkpoint.

    Returns:
        Dict with train_bpb, val_bpb, core_metric, core_tasks, and
        optionally custom_eval results.
    """
    import json
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.chdir(NANOCHAT_DIR)

    checkout_ref(nanochat_ref)

    # Reload volume to see checkpoints written by training containers
    volume.reload()

    results = {"checkpoint_tag": checkpoint_tag, "step": step}

    # --- Standard evals ---
    cmd = [
        "python", "-m", "scripts.base_eval",
        f"--eval={standard_evals}",
        f"--model-tag={checkpoint_tag}",
        f"--step={step}",
    ]
    print(f"[eval] Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        proc.check_returncode()

    results.update(parse_eval_stdout(proc.stdout, standard_evals))

    # [M4] Rename CORE CSV to include model_tag (prevents filename collision)
    src = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"base_model_{step:06d}.csv")
    dst = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"{checkpoint_tag}_{step:06d}.csv")
    if os.path.exists(src):
        os.rename(src, dst)
        print(f"[eval] Renamed CSV: {os.path.basename(src)} → {os.path.basename(dst)}")

    core_tasks = parse_core_csv(dst)
    if core_tasks:
        results["core_tasks"] = core_tasks

    # --- Custom eval (direct import, no subprocess) ---
    if custom_eval_script:
        import sys

        sys.path.insert(0, "/root/evals")
        sys.path.insert(0, NANOCHAT_DIR)
        from context_length_eval import run_eval

        print("[eval] Running custom: context_length_eval.run_eval()")
        custom_result = run_eval(
            checkpoint_dir=VOLUME_PATH,
            model_tag=checkpoint_tag,
            step=step,
        )
        results["custom_eval"] = custom_result

        # [M2] Persist custom eval JSON to Volume
        custom_eval_dir = os.path.join(VOLUME_PATH, CUSTOM_EVAL_SUBDIR)
        os.makedirs(custom_eval_dir, exist_ok=True)
        out_path = os.path.join(custom_eval_dir, f"{checkpoint_tag}_{step:06d}.json")
        with open(out_path, "w") as f:
            json.dump(custom_result, f, indent=2)
        print(f"[eval] Custom eval saved: {out_path}")

    volume.commit()
    return results
