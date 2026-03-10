"""Collect tool: pull eval JSONs from Modal Volume and training metrics from W&B.

Usage:
    python -m a4.p4.scripts.collect --config a4/p4/configs/collect.yaml
    python -m a4.p4.scripts.collect --config a4/p4/configs/collect.yaml --eval-only
    python -m a4.p4.scripts.collect --config a4/p4/configs/collect.yaml --wandb-only

Config YAML format:
    output_dir: a4/p4/results/collected
    volume_name: a3-checkpoints
    wandb_project: 490-autobook-a4
    runs:
      - name: baseline
        checkpoint_tag: p4-baseline
        eval_step: 467
        wandb_run_id: abc123
      - name: separate_a
        checkpoint_tag: p4-separate-a
        eval_step: 467
        wandb_run_id: def456
      ...
"""

import argparse
import json
import os
import subprocess
import sys


def load_config(config_path: str) -> dict:
    """Load collect configuration from YAML."""
    import yaml

    with open(config_path) as f:
        return yaml.safe_load(f)


def collect_eval(run_cfg: dict, volume_name: str, output_dir: str) -> str | None:
    """Download custom eval JSON from Modal Volume for one run.

    Returns local path to downloaded file, or None on failure.
    """
    tag = run_cfg["checkpoint_tag"]
    step = run_cfg["eval_step"]
    name = run_cfg["name"]

    # Custom eval JSON lives at custom_evals/{tag}_{step:06d}.json on the volume
    remote_path = f"custom_evals/{tag}_{step:06d}.json"
    local_path = os.path.join(output_dir, "eval", f"{name}.json")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Also try with custom output name if specified
    custom_name = run_cfg.get("eval_output_name")
    if custom_name:
        remote_path = f"custom_evals/{custom_name}"

    print(f"[collect] {name}: downloading {remote_path} from volume '{volume_name}'")
    result = subprocess.run(
        ["modal", "volume", "get", volume_name, remote_path, local_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[collect] {name}: FAILED — {result.stderr.strip()}")
        return None

    print(f"[collect] {name}: saved to {local_path}")
    return local_path


def collect_wandb(run_cfg: dict, wandb_project: str, output_dir: str) -> str | None:
    """Download training metrics from W&B for one run.

    Pulls: step, mean_reward, per-component rewards, mean_seq_length.
    Returns local path to saved JSON, or None on failure.
    """
    try:
        import wandb
    except ImportError:
        print("[collect] wandb not installed — skipping W&B collection")
        return None

    run_id = run_cfg.get("wandb_run_id")
    name = run_cfg["name"]
    if not run_id:
        print(f"[collect] {name}: no wandb_run_id specified, skipping W&B")
        return None

    print(f"[collect] {name}: fetching W&B run {run_id} from {wandb_project}")
    api = wandb.Api()
    try:
        # wandb_project format: "entity/project" or just "project"
        run = api.run(f"{wandb_project}/{run_id}")
    except Exception as e:
        print(f"[collect] {name}: W&B lookup failed — {e}")
        return None

    # Pull training history — all logged scalars
    # chat_rl.py logs: "reward", "reward/{name}", "sequence_length"
    # We normalize to: "mean_reward", "reward/{name}", "mean_seq_length"
    KEY_NORMALIZE = {
        "reward": "mean_reward",
        "sequence_length": "mean_seq_length",
    }
    history = run.scan_history()
    rows = []
    for row in history:
        entry = {"_step": row.get("_step")}
        for key in row:
            if key in KEY_NORMALIZE:
                entry[KEY_NORMALIZE[key]] = row[key]
            elif key.startswith("reward/"):
                entry[key] = row[key]
        # Only keep rows that have at least one metric we care about
        if len(entry) > 1:
            rows.append(entry)

    local_path = os.path.join(output_dir, "wandb", f"{name}.json")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w") as f:
        json.dump({"run_id": run_id, "run_name": name, "history": rows}, f, indent=2)

    print(f"[collect] {name}: saved {len(rows)} W&B rows to {local_path}")
    return local_path


def collect_all(config: dict, eval_only: bool = False, wandb_only: bool = False):
    """Run collection for all runs in config."""
    output_dir = config["output_dir"]
    volume_name = config.get("volume_name", "a3-checkpoints")
    wandb_project = config.get("wandb_project", "490-autobook-a4")
    runs = config["runs"]

    os.makedirs(output_dir, exist_ok=True)

    results = {"runs": {}}

    for run_cfg in runs:
        name = run_cfg["name"]
        run_result = {}

        if not wandb_only:
            eval_path = collect_eval(run_cfg, volume_name, output_dir)
            run_result["eval_path"] = eval_path

        if not eval_only:
            wandb_path = collect_wandb(run_cfg, wandb_project, output_dir)
            run_result["wandb_path"] = wandb_path

        results["runs"][name] = run_result

    # Save manifest
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[collect] Manifest saved to {manifest_path}")

    # Summary
    print(f"\n[collect] Summary:")
    for name, res in results["runs"].items():
        eval_ok = res.get("eval_path") is not None
        wandb_ok = res.get("wandb_path") is not None
        parts = []
        if not wandb_only:
            parts.append(f"eval={'OK' if eval_ok else 'MISSING'}")
        if not eval_only:
            parts.append(f"wandb={'OK' if wandb_ok else 'MISSING'}")
        print(f"  {name}: {', '.join(parts)}")


def main():
    parser = argparse.ArgumentParser(description="Collect eval results and W&B metrics")
    parser.add_argument("--config", required=True, help="Path to collect config YAML")
    parser.add_argument("--eval-only", action="store_true", help="Only collect eval JSONs")
    parser.add_argument("--wandb-only", action="store_true", help="Only collect W&B metrics")
    args = parser.parse_args()

    config = load_config(args.config)
    collect_all(config, eval_only=args.eval_only, wandb_only=args.wandb_only)


if __name__ == "__main__":
    main()
