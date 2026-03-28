from __future__ import annotations

from ml_workspace.training.runners.train import Train
from ml_workspace.training.shared.infra import VOLUME_PATH, app, image, volume


@app.function(image=image, volumes={VOLUME_PATH: volume}, timeout=24 * 3600)
def run(cfg: dict) -> dict:
    resolved_gpu = cfg.get("gpu", "A10G")
    print(f"Resolved GPU: {resolved_gpu}")
    print(f"Output subdir: {cfg.get('output_subdir', 'autobook_deberta')}")
    train = Train.with_options(
        gpu=resolved_gpu,
        timeout=int(cfg.get("timeout_hours", 4) * 3600),
    )()

    sequence_result = None
    entity_result = None

    if cfg.get("sequence", {}).get("enabled", True):
        sequence_cfg = {
            **cfg,
            **cfg.get("sequence", {}),
        }
        sequence_result = train.run_sequence.remote(sequence_cfg)

    if cfg.get("entity", {}).get("enabled", True):
        entity_cfg = {
            **cfg,
            **cfg.get("entity", {}),
        }
        entity_result = train.run_entity.remote(entity_cfg)

    evaluation_result = None
    if cfg.get("evaluation", {}).get("enabled", False) and cfg.get("test_path"):
        evaluation_result = train.run_evaluation.remote(cfg)

    return {
        "experiment_name": cfg.get("experiment_name", "autobook_ml"),
        "sequence": sequence_result,
        "entity": entity_result,
        "evaluation": evaluation_result,
    }
