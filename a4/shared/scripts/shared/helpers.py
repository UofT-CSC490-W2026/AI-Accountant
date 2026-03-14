"""Pure Python helpers — no Modal imports, testable locally."""

import csv
import glob
import os
import re

CKPT_STEP_RE = re.compile(r"model_(\d+)\.pt$")


def checkout_ref(ref: str):
    """Fetch latest refs and checkout target. Used inside Modal containers."""
    import subprocess

    subprocess.run(["git", "fetch", "origin", "--tags"], check=True)
    subprocess.run(["git", "checkout", ref], check=True)


def find_final_step(checkpoint_dir: str, ckpt_subdir: str, model_tag: str) -> int:
    """Find the highest step number from checkpoint files."""
    tag_dir = os.path.join(checkpoint_dir, ckpt_subdir, model_tag)
    checkpoint_files = glob.glob(os.path.join(tag_dir, "model_*.pt"))
    if not checkpoint_files:
        raise FileNotFoundError(f"No checkpoints found in {tag_dir}")

    steps = []
    for f in checkpoint_files:
        m = CKPT_STEP_RE.search(os.path.basename(f))
        if m:
            steps.append(int(m.group(1)))
    if not steps:
        raise FileNotFoundError(f"No valid checkpoint files in {tag_dir}")
    return max(steps)


def partition_stages(stages: list) -> tuple[list, list]:
    """Split stages into (independent, dependent) based on depends_on field."""
    independent = [s for s in stages if "depends_on" not in s]
    dependent = [s for s in stages if "depends_on" in s]
    return independent, dependent


def resolve_eval_inputs(
    eval_entries: list,
    stage_results: dict,
    nanochat_ref: str,
) -> list:
    """Build eval input tuples from config + stage results.

    Handles:
    - Endpoint evals (after_stage or explicit step)
    - recovery_curve blocks (M3): generates intermediate eval entries
      dynamically at checkpoint positions (multiples of save interval).

    Returns list of tuples:
    (nanochat_ref, checkpoint, step, standard_evals, custom_script, max_per_task, custom_eval_output_name, num_eval_shards, eval_env)
    """
    eval_inputs = []

    for entry in eval_entries:
        checkpoint = entry["checkpoint"]

        # Determine step
        after_stage = entry.get("after_stage")
        if after_stage:
            if after_stage not in stage_results:
                raise ValueError(f"Eval after_stage '{after_stage}' not found in stage results")
            step = stage_results[after_stage]["final_step"]
        else:
            step = entry["step"]

        # Standard evals
        evals = entry.get("evals", [])
        standard = [e for e in evals if e in ("bpb", "core")]
        standard_evals = ",".join(standard)
        custom_script = entry.get("custom_eval") if "custom" in evals else None
        max_per_task = int(entry.get("max_per_task", -1))
        custom_eval_output_name = entry.get("custom_eval_output_name")
        num_eval_shards = int(entry.get("num_eval_shards", 1))
        eval_env = entry.get("eval_env") or {}

        eval_inputs.append(
            (
                nanochat_ref,
                checkpoint,
                step,
                standard_evals,
                custom_script,
                max_per_task,
                custom_eval_output_name,
                num_eval_shards,
                eval_env,
            )
        )

        # Recovery curve — generate intermediate checkpoint evals dynamically
        if "recovery_curve" in entry:
            rc = entry["recovery_curve"]
            dep_name = rc["depends_on"]
            if dep_name not in stage_results:
                raise ValueError(f"recovery_curve depends_on '{dep_name}' not found in stage results")
            start_step = stage_results[dep_name]["final_step"]
            end_step = step  # endpoint of this eval entry's stage
            interval = rc["interval"]
            rc_custom = rc.get("custom_eval")

            # Snap to next multiple of interval (checkpoints at step % save_every == 0)
            first = ((start_step // interval) + 1) * interval
            for rc_step in range(first, end_step, interval):
                eval_inputs.append((nanochat_ref, checkpoint, rc_step, "bpb", rc_custom, -1, None, 1, {}))

    return eval_inputs


def parse_eval_stdout(stdout: str, standard_evals: str = "bpb,core") -> dict:
    """Extract BPB and CORE metrics from base_eval stdout.

    Only warns about metrics that were actually requested.
    """
    results = {}
    for line in stdout.splitlines():
        if "train bpb:" in line:
            results["train_bpb"] = float(line.split(":")[-1].strip())
        elif "val bpb:" in line:
            results["val_bpb"] = float(line.split(":")[-1].strip())
        elif "CORE metric:" in line:
            results["core_metric"] = float(line.split(":")[-1].strip())

    requested = set(standard_evals.split(","))
    if "bpb" in requested:
        for key in ("train_bpb", "val_bpb"):
            if key not in results:
                print(f"[eval] WARNING: '{key}' not found in base_eval output")
    if "core" in requested and "core_metric" not in results:
        print(f"[eval] WARNING: 'core_metric' not found in base_eval output")

    return results


def parse_core_csv(csv_path: str) -> dict:
    """Parse per-task CORE results from nanochat's CSV output."""
    if not os.path.exists(csv_path):
        return {}

    tasks = {}
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
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
