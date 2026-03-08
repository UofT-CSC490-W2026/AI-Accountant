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
from shared.helpers import checkout_ref, find_final_step


@app.cls(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="H100",
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

        # [1.1] Optional init copy: branch checkpoints to a new model tag before training
        _maybe_init_checkpoint_branch(args)

        # [2] Git hash: record which nanochat commit is being trained
        git_hash = _get_git_hash()

        # [3] Train: build CLI from args and run nanochat
        script = args.get("script", "scripts.base_train")
        model_tag = _resolve_model_tag(args)
        ckpt_subdir = _checkpoint_subdir_for_script(script)
        prev_final_step = _safe_find_final_step(model_tag, ckpt_subdir)

        cmd = _build_cli(args)
        subprocess.run(cmd, check=True)

        # [4] Final step: discover from filesystem to support scripts where
        #     num_iterations may be -1 (e.g. chat_sft full-epoch mode).
        final_step = find_final_step(VOLUME_PATH, ckpt_subdir, model_tag)
        if prev_final_step is not None and final_step <= prev_final_step:
            raise RuntimeError(
                f"No new checkpoint detected for '{model_tag}' in '{ckpt_subdir}'. "
                f"Before run: {prev_final_step}, after run: {final_step}."
            )
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
    script = args.get("script", "scripts.base_train")
    cmd = ["python", "-m", script]
    reserved = {
        "script",
        "init_from_source",
        "init_from_tag",
        "init_from_step",
    }
    for key, value in args.items():
        if key in reserved:
            continue
        cli_key = key.replace("_", "-")
        if isinstance(value, bool):
            # argparse store_true/store_false flags should be passed without "=value"
            if value:
                cmd.append(f"--{cli_key}")
            continue
        cmd.append(f"--{cli_key}={value}")
    print(f"[train] Running: {' '.join(cmd)}")
    return cmd


def _resolve_model_tag(args: dict) -> str:
    model_tag = args.get("model_tag")
    if model_tag:
        return model_tag
    if "depth" in args:
        return f"d{args['depth']}"
    raise KeyError("Missing required training arg: model_tag (or depth fallback).")


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


def _checkpoint_subdir_for_script(script: str) -> str:
    if script == "scripts.base_train" or "base_train" in script:
        return CKPT_SUBDIR
    if script == "scripts.chat_sft" or "chat_sft" in script:
        return "chatsft_checkpoints"
    if script == "scripts.chat_rl" or "chat_rl" in script:
        return "chatrl_checkpoints"
    return CKPT_SUBDIR


def _init_destination_subdir(script: str, init_from_source: str) -> str:
    """Choose where seeded checkpoints should be copied.

    For chat_sft, nanochat loads the starting checkpoint from source="base",
    so init copies must land in base_checkpoints, even though outputs are saved
    to chatsft_checkpoints.
    """
    if _checkpoint_subdir_for_script(script) == "chatsft_checkpoints":
        return "base_checkpoints"
    return {
        "base": "base_checkpoints",
        "sft": "chatsft_checkpoints",
        "rl": "chatrl_checkpoints",
    }[init_from_source]


def _safe_find_final_step(model_tag: str, ckpt_subdir: str) -> int | None:
    try:
        return find_final_step(VOLUME_PATH, ckpt_subdir, model_tag)
    except FileNotFoundError:
        return None


def _copy_if_missing(src: str, dst: str):
    import os
    import shutil

    if os.path.exists(dst):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def _sanitize_meta_model_config(meta_path: str):
    """Drop unsupported model_config keys for the checked-out nanochat ref."""
    import inspect
    import json
    import os

    if not os.path.exists(meta_path):
        return

    try:
        from nanochat.gpt import GPTConfig  # type: ignore
    except Exception as e:
        print(f"[train] WARNING: could not import GPTConfig for meta sanitization: {e}")
        return

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    model_cfg = meta.get("model_config")
    if not isinstance(model_cfg, dict):
        return

    supported = set(inspect.signature(GPTConfig).parameters.keys())
    dropped = sorted([k for k in list(model_cfg.keys()) if k not in supported])
    if not dropped:
        return

    for k in dropped:
        model_cfg.pop(k, None)
    meta["model_config"] = model_cfg

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[train] Sanitized meta config at {meta_path}; dropped unsupported keys: {dropped}")


def _maybe_init_checkpoint_branch(args: dict):
    """Optionally copy a source checkpoint into a new tag before training.

    Expected args:
      - init_from_source: base|sft|rl (default: base)
      - init_from_tag: source model tag
      - init_from_step: source checkpoint step
    """
    import glob
    import os

    init_from_tag = args.get("init_from_tag")
    init_from_step = args.get("init_from_step")
    if not init_from_tag or init_from_step is None:
        return

    init_from_source = args.get("init_from_source", "base")
    source_subdir = {
        "base": "base_checkpoints",
        "sft": "chatsft_checkpoints",
        "rl": "chatrl_checkpoints",
    }[init_from_source]
    script = args.get("script", "scripts.base_train")
    target_subdir = _init_destination_subdir(script, init_from_source)
    target_tag = _resolve_model_tag(args)

    src_dir = os.path.join(VOLUME_PATH, source_subdir, init_from_tag)
    dst_dir = os.path.join(VOLUME_PATH, target_subdir, target_tag)

    print(
        f"[train] Initializing '{target_subdir}/{target_tag}' from "
        f"'{source_subdir}/{init_from_tag}' @ step {init_from_step}"
    )

    model_name = f"model_{init_from_step:06d}.pt"
    meta_name = f"meta_{init_from_step:06d}.json"

    _copy_if_missing(os.path.join(src_dir, model_name), os.path.join(dst_dir, model_name))
    dst_meta = os.path.join(dst_dir, meta_name)
    _copy_if_missing(os.path.join(src_dir, meta_name), dst_meta)
    _sanitize_meta_model_config(dst_meta)

    # Copy all optimizer rank shards for that step if present.
    for src_optim in glob.glob(os.path.join(src_dir, f"optim_{init_from_step:06d}_rank*.pt")):
        dst_optim = os.path.join(dst_dir, os.path.basename(src_optim))
        _copy_if_missing(src_optim, dst_optim)
