"""Eval class — one checkpoint per GPU."""

import modal

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


@app.cls(
    image=eval_image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="A100-80GB",
)
class Evaluate:
    @modal.method()
    def run(
        self,
        nanochat_ref: str,
        checkpoint_tag: str,
        step: int,
        standard_evals: str = "bpb,core",
        custom_eval_script: str | None = None,
        max_per_task: int = -1,
    ) -> dict:
        """Run standard evals and optionally a custom eval on one checkpoint.

        1. Set up environment and reload the volume.
        2. Run standard evals (BPB and/or CORE).
        3. Rename CORE CSV and parse per-task scores.
        4. Run custom eval if specified and save results as JSON.
        5. Commit eval results to the volume.

        Args:
            nanochat_ref: Git ref (branch or tag) to checkout in the nanochat fork.
            checkpoint_tag: Model tag (checkpoint folder name, e.g. "pico-short").
            step: Checkpoint step number to evaluate.
            standard_evals: Comma-separated eval names ("bpb", "core", or "bpb,core").
            custom_eval_script: Path to a custom eval script, or None to skip.
            max_per_task: Max examples per CORE task (-1 = full task).

        Returns:
            Dict with train_bpb, val_bpb, core_metric, core_tasks, and
            optionally custom_eval results.
        """
        import os

        # [1] Environment: set up paths and checkout the requested nanochat ref
        os.environ["NANOCHAT_BASE_DIR"] = VOLUME_PATH
        os.chdir(NANOCHAT_DIR)
        checkout_ref(nanochat_ref)

        # [2] Reload volume: pick up checkpoints written by training containers
        volume.reload()

        results = {"checkpoint_tag": checkpoint_tag, "step": step}

        # [3] Standard evals: run BPB and/or CORE and parse results
        if standard_evals:
            results.update(_run_standard_evals(checkpoint_tag, step, standard_evals, max_per_task))

        # [3.1] Rename CSV: add model_tag to prevent collisions across checkpoints
        _rename_core_csv(checkpoint_tag, step)

        # [3.2] Parse CSV: extract per-task CORE scores
        csv_path = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"{checkpoint_tag}_{step:06d}.csv")
        core_tasks = parse_core_csv(csv_path)
        if core_tasks:
            results["core_tasks"] = core_tasks

        # [4] Custom eval: run user-provided eval script if specified
        if custom_eval_script:
            custom_result = _run_custom_eval(custom_eval_script, checkpoint_tag, step)
            results["custom_eval"] = custom_result
            _save_custom_eval(checkpoint_tag, step, custom_result)

        # [5] Commit: persist eval results to the volume
        volume.commit()
        return results







# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_standard_evals(checkpoint_tag: str, step: int, standard_evals: str, max_per_task: int = -1) -> dict:
    """Run nanochat's built-in BPB and/or CORE benchmarks."""
    import subprocess

    cmd = [
        "python", "-m", "scripts.base_eval",
        f"--eval={standard_evals}",
        f"--model-tag={checkpoint_tag}",
        f"--step={step}",
    ]
    if "core" in standard_evals and max_per_task > 0:
        cmd.append(f"--max-per-task={max_per_task}")
    print(f"[eval] Running: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    stdout_lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        stdout_lines.append(line)

    returncode = proc.wait()
    stdout_text = "".join(stdout_lines)
    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd, output=stdout_text)

    return parse_eval_stdout(stdout_text, standard_evals)


def _rename_core_csv(checkpoint_tag: str, step: int):
    """Rename CORE CSV from generic name to include model_tag."""
    import os

    src = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"base_model_{step:06d}.csv")
    dst = os.path.join(VOLUME_PATH, EVAL_SUBDIR, f"{checkpoint_tag}_{step:06d}.csv")
    if os.path.exists(src):
        os.rename(src, dst)
        print(f"[eval] Renamed CSV: {os.path.basename(src)} → {os.path.basename(dst)}")


def _run_custom_eval(custom_eval_script: str, checkpoint_tag: str, step: int) -> dict:
    """Import and run the user-provided eval script."""
    import importlib
    import os
    import sys

    sys.path.insert(0, "/root/evals")
    sys.path.insert(0, NANOCHAT_DIR)

    module_name = os.path.splitext(os.path.basename(custom_eval_script))[0]
    mod = importlib.import_module(module_name)

    print(f"[eval] Running custom: {module_name}.run_eval()")
    return mod.run_eval(
        checkpoint_dir=VOLUME_PATH,
        model_tag=checkpoint_tag,
        step=step,
    )


def _save_custom_eval(checkpoint_tag: str, step: int, custom_result: dict):
    """Save custom eval results as JSON on the volume."""
    import json
    import os

    custom_eval_dir = os.path.join(VOLUME_PATH, CUSTOM_EVAL_SUBDIR)
    os.makedirs(custom_eval_dir, exist_ok=True)
    out_path = os.path.join(custom_eval_dir, f"{checkpoint_tag}_{step:06d}.json")
    with open(out_path, "w") as f:
        json.dump(custom_result, f, indent=2)
    print(f"[eval] Custom eval saved: {out_path}")
