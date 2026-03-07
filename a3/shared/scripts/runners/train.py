"""Training class — one stage per GPU."""

import modal

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
from shared.helpers import checkout_ref


@app.cls(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100-80GB",
)
class Train:
    @modal.method()
    def run(self, nanochat_ref: str, args: dict) -> dict:
        """Run nanochat base training for one stage.

        1. Set up environment and checkout the nanochat ref.
        2. Record the git commit hash.
        3. Build CLI command from args and run training.
        4. Find the final checkpoint step.
        5. Attach git hash to the W&B run.
        6. Commit checkpoints to the volume.

        Args:
            nanochat_ref: Git ref (branch or tag) to checkout in the nanochat fork.
            args: Dict mapping nanochat CLI arg names (underscore form) to values.

        Returns:
            Dict with model_tag, final_step, and git_hash.
        """
        import os
        import subprocess

        # [1] Environment: set up paths and checkout the requested nanochat ref
        os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
        os.environ["WANDB_PROJECT"] = WANDB_PROJECT
        os.chdir(NANOCHAT_DIR)
        checkout_ref(nanochat_ref)

        # [2] Git hash: record which nanochat commit is being trained
        git_hash = _get_git_hash()

        # [3] Train: build CLI from args and run nanochat
        cmd = _build_cli(args)
        subprocess.run(cmd, check=True)

        # [4] Final step: use num_iterations (the target step nanochat trained to).
        #     Avoids stale checkpoints on the Volume from prior runs.
        model_tag = args.get("model_tag", f"d{args['depth']}")
        final_step = args["num_iterations"]
        print(f"[train] Final step: {final_step}")

        # [5] W&B metadata: attach git hash to the W&B run for reproducibility
        _log_git_hash_to_wandb(args.get("run"), git_hash)

        # [6] Commit: persist checkpoints to the volume
        volume.commit()

        return {
            "model_tag": model_tag,
            "final_step": final_step,
            "git_hash": git_hash,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_cli(args: dict) -> list[str]:
    """Convert underscore args to kebab-case CLI flags."""
    script = args.pop("script", "scripts.base_train")
    cmd = ["python", "-m", script]
    for key, value in args.items():
        cli_key = key.replace("_", "-")
        cmd.append(f"--{cli_key}={value}")
    print(f"[train] Running: {' '.join(cmd)}")
    return cmd


def _get_git_hash() -> str:
    import subprocess

    git_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    print(f"[train] nanochat commit: {git_hash}")
    return git_hash


def _log_git_hash_to_wandb(run_name: str | None, git_hash: str):
    if not run_name or run_name == "dummy":
        return
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
