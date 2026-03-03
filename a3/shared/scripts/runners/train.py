"""Training function — one stage per GPU."""

from shared.infra import (
    CKPT_SUBDIR,
    NANOCHAT_DIR,
    VOLUME_PATH,
    WANDB_PROJECT,
    app,
    image,
    volume,
    wandb_secret,
)
from shared.helpers import checkout_ref, find_final_step


@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100-80GB",
    timeout=3 * 3600,
)
def train(nanochat_ref: str, args: dict) -> dict:
    """Run nanochat base training for one stage.

    Args:
        nanochat_ref: Git ref (branch or tag) to checkout in the nanochat fork.
        args: Dict mapping nanochat CLI arg names (underscore form) to values.

    Returns:
        Dict with model_tag, final_step, and git_hash.
    """
    import os
    import subprocess

    os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
    os.environ["WANDB_PROJECT"] = WANDB_PROJECT
    os.chdir(NANOCHAT_DIR)

    checkout_ref(nanochat_ref)

    # Record commit hash
    git_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"[train] nanochat commit: {git_hash}")

    # Build CLI command: convert underscore keys to kebab-case flags
    script = args.pop("script", "scripts.base_train")
    cmd = ["python", "-m", script]
    for key, value in args.items():
        cli_key = key.replace("_", "-")
        cmd.append(f"--{cli_key}={value}")

    print(f"[train] Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # Determine final step from checkpoint files
    model_tag = args.get("model_tag", f"d{args['depth']}")
    final_step = find_final_step(VOLUME_PATH, CKPT_SUBDIR, model_tag)
    print(f"[train] Final step: {final_step}")

    # Log git hash to W&B run
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
            print(f"[train] WARNING: could not update W&B with git hash: {e}")

    volume.commit()

    return {
        "model_tag": model_tag,
        "final_step": final_step,
        "git_hash": git_hash,
    }
