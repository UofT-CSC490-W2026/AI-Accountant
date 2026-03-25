from __future__ import annotations

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
    """
    Scaffold for the future trained sequence-classification stack.

    The repo can wire this class in now without changing downstream contracts.
    Actual artifact loading and forward passes can be added later.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path

    @property
    def is_ready(self) -> bool:
        return bool(self.model_path)

    def _not_ready(self) -> ModelNotReadyError:
        return ModelNotReadyError(
            "DeBERTa classifier scaffold is configured, but trained-model inference is not implemented yet."
        )

    def predict_intent(self, text: str, source: str) -> ClassificationResult:
        raise self._not_ready()

    def predict_bank_category(self, text: str, intent_label: str | None) -> ClassificationResult:
        raise self._not_ready()

    def predict_cca_class(self, intent_label: str | None, asset_name: str | None) -> ClassificationResult:
        raise self._not_ready()
