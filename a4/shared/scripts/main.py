"""Local entrypoint — parses YAML config and dispatches to Modal.

Usage:
    modal run a3/shared/scripts/main.py --config a3/p3/configs/p3_baseline.yaml

With --detach, the pipeline runs entirely on Modal (survives local disconnects):
    modal run --detach a3/shared/scripts/main.py --config ...
"""

import yaml

from shared.infra import app  # noqa: F401 — registers all Modal functions
from runners.run import run  # noqa: F401


@app.local_entrypoint()
def main(config: str):
    """
    1. Load config from the YAML provided by arg.
    2. Launch the experiment on Modal.
    3. Print results.
    """

    # [1] Load config: read the YAML file
    with open(config) as f:
        cfg = yaml.safe_load(f)
    experiment_name = cfg.get("experiment_name", "experiment")
    
    # [2] Launch: log experiment name and dispatch to Modal
    _print_launch(experiment_name)
    results = run.remote(cfg)

    # [3] Results: print summary locally (only reached without --detach)
    _print_results(experiment_name, results)





# ---------------------------------------------------------------------------
# Formatting helpers -- not important
# ---------------------------------------------------------------------------

def _print_launch(experiment_name: str):
    print(f"Launching pipeline: {experiment_name}")
    print("Tip: use 'modal run --detach ...' to survive local disconnects.\n")


def _print_results(experiment_name: str, results: dict):
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
        err = res.get("error")
        if err:
            print(f"  eval[{i}] {tag}@{s}: FAILED — {err}")
        else:
            print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")
