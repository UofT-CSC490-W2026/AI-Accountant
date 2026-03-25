from __future__ import annotations

from abc import ABC, abstractmethod

from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult


class ModelNotReadyError(RuntimeError):
    """Raised when a scaffolded trained-model provider has no usable artifact yet."""


class MLInferenceProvider(ABC):
    @abstractmethod
    def enrich(self, message: dict) -> dict:
        raise NotImplementedError


class SequenceClassifier(ABC):
    @property
    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def predict_intent(self, text: str, source: str) -> ClassificationResult:
        raise NotImplementedError

    @abstractmethod
    def predict_bank_category(self, text: str, intent_label: str | None) -> ClassificationResult:
        raise NotImplementedError

    @abstractmethod
    def predict_cca_class(self, intent_label: str | None, asset_name: str | None) -> ClassificationResult:
        raise NotImplementedError


class EntityExtractor(ABC):
    @property
    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        raise NotImplementedError
