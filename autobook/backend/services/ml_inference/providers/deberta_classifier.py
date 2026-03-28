from __future__ import annotations

import json
from pathlib import Path

from services.ml_inference.providers.base import ModelNotReadyError, SequenceClassifier
from services.ml_inference.schemas import ClassificationResult

INTENT_LABELS = (
    "asset_purchase",
    "software_subscription",
    "rent_expense",
    "meals_entertainment",
    "professional_fees",
    "bank_fee",
    "transfer",
    "bank_transaction",
    "general_expense",
)

BANK_CATEGORY_LABELS = (
    "transfer",
    "equipment",
    "software_subscription",
    "rent",
    "meals_entertainment",
    "professional_fees",
    "bank_fees",
)

CCA_CLASS_LABELS = ("class_50", "class_8")


class DebertaSequenceClassifier(SequenceClassifier):
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._pipelines: dict[str, object] = {}

    @property
    def is_ready(self) -> bool:
        if not self.model_path:
            return False
        root = Path(self.model_path)
        return (root / "intent_label").exists()

    def _require_ready(self) -> Path:
        if not self.model_path:
            raise ModelNotReadyError("DeBERTa classifier path is not configured.")
        root = Path(self.model_path)
        if not root.exists():
            raise ModelNotReadyError(f"DeBERTa classifier path does not exist: {root}")
        return root

    def _task_dir(self, task_name: str) -> Path:
        root = self._require_ready()
        task_dir = root / task_name
        if not task_dir.exists():
            raise ModelNotReadyError(f"Missing trained classifier artifact for task {task_name!r}: {task_dir}")
        return task_dir

    def _load_pipeline(self, task_name: str):
        if task_name in self._pipelines:
            return self._pipelines[task_name]

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception as exc:
            raise ModelNotReadyError("transformers/torch are not available for DeBERTa classifier loading.") from exc

        task_dir = self._task_dir(task_name)
        tokenizer = AutoTokenizer.from_pretrained(task_dir)
        model = AutoModelForSequenceClassification.from_pretrained(task_dir)
        model.eval()
        pipeline = {
            "torch": torch,
            "tokenizer": tokenizer,
            "model": model,
        }
        self._pipelines[task_name] = pipeline
        return pipeline

    def _predict_label(self, task_name: str, text: str) -> ClassificationResult:
        pipeline = self._load_pipeline(task_name)
        torch = pipeline["torch"]
        tokenizer = pipeline["tokenizer"]
        model = pipeline["model"]

        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            logits = model(**encoded).logits
            probabilities = torch.softmax(logits, dim=-1)[0]
            index = int(torch.argmax(probabilities).item())
            confidence = float(probabilities[index].item())

        label = model.config.id2label.get(index)
        if label in {None, "__null__"}:
            return ClassificationResult(None, confidence)
        return ClassificationResult(str(label), confidence)

    def predict_intent(self, text: str, source: str) -> ClassificationResult:
        return self._predict_label("intent_label", f"source: {source} text: {text}")

    def predict_bank_category(self, text: str, intent_label: str | None) -> ClassificationResult:
        raise ModelNotReadyError("Bank-category prediction is heuristic-only in the current trained model setup.")

    def predict_cca_class(self, intent_label: str | None, asset_name: str | None) -> ClassificationResult:
        raise ModelNotReadyError("CCA-class prediction is heuristic-only in the current trained model setup.")
