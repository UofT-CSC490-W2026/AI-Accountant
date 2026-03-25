from __future__ import annotations

from functools import lru_cache

from config import get_settings
from services.ml_inference.providers import (
    BaselineInferenceService,
    DebertaEntityExtractor,
    DebertaSequenceClassifier,
    ModelNotReadyError,
)
from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult


class HybridInferenceService(BaselineInferenceService):
    """
    Contract-preserving ML layer that can blend trained components in later.

    Today it falls back to the baseline heuristics whenever a trained component
    is absent or not yet implemented.
    """

    def __init__(
        self,
        *,
        sequence_classifier: DebertaSequenceClassifier | None = None,
        entity_extractor: DebertaEntityExtractor | None = None,
    ) -> None:
        self.sequence_classifier = sequence_classifier
        self.entity_extractor = entity_extractor

    def classify_intent(self, text: str, source: str) -> ClassificationResult:
        classifier = self.sequence_classifier
        if classifier is not None and classifier.is_ready:
            try:
                return classifier.predict_intent(text, source)
            except ModelNotReadyError:
                pass
        return super().classify_intent(text, source)

    def classify_bank_transaction(self, text: str, intent_label: str | None) -> ClassificationResult:
        classifier = self.sequence_classifier
        if classifier is not None and classifier.is_ready:
            try:
                return classifier.predict_bank_category(text, intent_label)
            except ModelNotReadyError:
                pass
        return super().classify_bank_transaction(text, intent_label)

    def match_cca_class(self, intent_label: str | None, asset_name: str | None) -> ClassificationResult:
        classifier = self.sequence_classifier
        if classifier is not None and classifier.is_ready:
            try:
                return classifier.predict_cca_class(intent_label, asset_name)
            except ModelNotReadyError:
                pass
        return super().match_cca_class(intent_label, asset_name)

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        extractor = self.entity_extractor
        if extractor is not None and extractor.is_ready:
            try:
                return extractor.extract_entities(message, text)
            except ModelNotReadyError:
                pass
        return super().extract_entities(message, text)


def build_inference_service(provider_name: str | None = None):
    settings = get_settings()
    provider = (provider_name or settings.ML_INFERENCE_PROVIDER).strip().lower()

    if provider == "heuristic":
        return BaselineInferenceService()

    if provider in {"hybrid", "deberta"}:
        return HybridInferenceService(
            sequence_classifier=DebertaSequenceClassifier(settings.ML_CLASSIFIER_MODEL_PATH),
            entity_extractor=DebertaEntityExtractor(settings.ML_ENTITY_MODEL_PATH),
        )

    raise ValueError(f"unsupported ML inference provider {provider!r}")


@lru_cache
def get_inference_service():
    return build_inference_service()


def enrich_message(message: dict) -> dict:
    return get_inference_service().enrich(message)
