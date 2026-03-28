from __future__ import annotations

import yaml

from ml_workspace.training.runners.run import run
from ml_workspace.training.shared.infra import app  # noqa: F401


@app.local_entrypoint()
def main(config: str):
    with open(config, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    print(f"Launching ML training pipeline: {cfg.get('experiment_name', 'autobook_ml')}")
    print("Tip: use 'modal run --detach ...' to survive local disconnects.\n")
    results = run.remote(cfg)
    print(results)
