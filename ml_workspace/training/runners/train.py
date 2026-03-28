from __future__ import annotations

import modal

from ml_workspace.training.shared.infra import (
    VOLUME_PATH,
    WANDB_PROJECT,
    app,
    image,
    volume,
    wandb_secret,
)


@app.cls(
    image=image,
    volumes={VOLUME_PATH: volume},
    secrets=[wandb_secret],
    gpu="H100",
)
class Train:
    @modal.method()
    def run_sequence(self, cfg: dict) -> dict:
        import os
        from pathlib import Path

        from ml_workspace.training.train_deberta_sequence import SequenceTrainingConfig, train_sequence_models

        os.environ["WANDB_PROJECT"] = cfg.get("wandb_project", WANDB_PROJECT)
        output_dir = Path(VOLUME_PATH) / cfg.get("output_subdir", "autobook_deberta") / "classifier"
        config = SequenceTrainingConfig(
            base_model=cfg["base_model"],
            train_path=Path(cfg["train_path"]),
            validation_path=Path(cfg["validation_path"]),
            output_dir=output_dir,
            num_train_epochs=float(cfg.get("num_train_epochs", 1.0)),
            learning_rate=float(cfg.get("learning_rate", 5e-5)),
            warmup_ratio=float(cfg.get("warmup_ratio", 0.1)),
            train_batch_size=int(cfg.get("train_batch_size", 4)),
            eval_batch_size=int(cfg.get("eval_batch_size", 4)),
            weight_decay=float(cfg.get("weight_decay", 0.01)),
            max_grad_norm=float(cfg.get("max_grad_norm", 1.0)),
            max_length=int(cfg.get("max_length", 256)),
            report_to_wandb=bool(cfg.get("report_to_wandb", False)),
            wandb_project=str(cfg.get("wandb_project", WANDB_PROJECT)),
            run_prefix=str(cfg.get("run_prefix", "autobook-seq")),
        )
        result = train_sequence_models(config)
        volume.commit()
        return result

    @modal.method()
    def run_entity(self, cfg: dict) -> dict:
        import os
        from pathlib import Path

        from ml_workspace.training.train_deberta_ner import EntityTrainingConfig, train_entity_model

        os.environ["WANDB_PROJECT"] = cfg.get("wandb_project", WANDB_PROJECT)
        output_dir = Path(VOLUME_PATH) / cfg.get("output_subdir", "autobook_deberta") / "entity_extractor"
        config = EntityTrainingConfig(
            base_model=cfg["base_model"],
            train_path=Path(cfg["train_path"]),
            validation_path=Path(cfg["validation_path"]),
            output_dir=output_dir,
            num_train_epochs=float(cfg.get("num_train_epochs", 1.0)),
            learning_rate=float(cfg.get("learning_rate", 5e-5)),
            warmup_ratio=float(cfg.get("warmup_ratio", 0.1)),
            train_batch_size=int(cfg.get("train_batch_size", 4)),
            eval_batch_size=int(cfg.get("eval_batch_size", 4)),
            weight_decay=float(cfg.get("weight_decay", 0.01)),
            max_grad_norm=float(cfg.get("max_grad_norm", 1.0)),
            max_length=int(cfg.get("max_length", 256)),
            report_to_wandb=bool(cfg.get("report_to_wandb", False)),
            wandb_project=str(cfg.get("wandb_project", WANDB_PROJECT)),
            run_name=str(cfg.get("run_name", "autobook-ner")),
        )
        result = train_entity_model(config)
        volume.commit()
        return result

    @modal.method()
    def run_evaluation(self, cfg: dict) -> dict:
        from pathlib import Path

        from ml_workspace.training.evaluate_saved_models import EvaluationConfig, evaluate_saved_models

        root = Path(VOLUME_PATH) / cfg.get("output_subdir", "autobook_deberta")
        evaluation_cfg = EvaluationConfig(
            classifier_dir=root / "classifier",
            entity_dir=root / "entity_extractor",
            test_path=Path(cfg["test_path"]),
            output_dir=root / cfg.get("evaluation", {}).get("output_subdir", "evaluation"),
        )
        result = evaluate_saved_models(evaluation_cfg)
        volume.commit()
        return result
