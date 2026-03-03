"""Local entrypoint — parses YAML config and dispatches to Modal.

Usage:
    modal run a3/shared/scripts/main.py --config a3/p3/configs/p3_baseline.yaml

With --detach, the pipeline runs entirely on Modal (survives local disconnects):
    modal run --detach a3/shared/scripts/main.py --config ...
"""

from shared.infra import app  # noqa: F401 — registers all Modal functions
from runners.run import remote  # noqa: F401


@app.local_entrypoint()
def main(config: str):
    """Launch the pipeline from a YAML config."""
    import yaml

    with open(config) as f:
        cfg = yaml.safe_load(f)

    experiment_name = cfg.get("experiment_name", "experiment")
    print(f"Launching pipeline: {experiment_name}")
    print("Tip: use 'modal run --detach ...' to survive local disconnects.\n")

    results = remote.remote(cfg)

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
        err = res.get("error")
        if err:
            print(f"  eval[{i}] {tag}@{s}: FAILED — {err}")
        else:
            print(f"  eval[{i}] {tag}@{s}: BPB={bpb}, CORE={core}")
    print("\nDone!")
