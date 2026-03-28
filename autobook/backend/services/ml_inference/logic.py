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

    def _preferred_vendor(
        self,
        message: dict,
        baseline: EntityExtractionResult,
        extracted: EntityExtractionResult,
    ) -> str | None:
        counterparty = message.get("counterparty")
        if isinstance(counterparty, str) and counterparty.strip():
            return counterparty.strip()

        preferred_party = self.select_party_mention(message)
        if preferred_party:
            return preferred_party

        return baseline.vendor or extracted.vendor

    def _preferred_mentioned_date(
        self,
        message: dict,
        text: str,
        baseline: EntityExtractionResult,
        extracted: EntityExtractionResult,
    ) -> str | None:
        preferred_date = self.extract_mentioned_date_from_message(message, text)
        if preferred_date:
            return preferred_date

        baseline_date = baseline.entities.get("mentioned_date")
        if isinstance(baseline_date, str) and baseline_date.strip():
            return baseline_date.strip()

        extracted_date = extracted.entities.get("mentioned_date")
        if isinstance(extracted_date, str) and extracted_date.strip():
            return extracted_date.strip()

        return None

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        baseline = super().extract_entities(message, text)
        extractor = self.entity_extractor
        if extractor is not None and extractor.is_ready:
            try:
                extracted = extractor.extract_entities(message, text)
                merged_entities = dict(baseline.entities)
                for key, value in dict(extracted.entities).items():
                    if value is not None and value != "" and value != [] and value != {}:
                        merged_entities[key] = value

                preferred_vendor = self._preferred_vendor(message, baseline, extracted)
                if preferred_vendor:
                    merged_entities["vendor"] = preferred_vendor

                preferred_mentioned_date = self._preferred_mentioned_date(message, text, baseline, extracted)
                if preferred_mentioned_date:
                    merged_entities["mentioned_date"] = preferred_mentioned_date

                return EntityExtractionResult(
                    amount=extracted.amount if extracted.amount is not None else baseline.amount,
                    vendor=preferred_vendor,
                    asset_name=extracted.asset_name or baseline.asset_name,
                    entities=merged_entities,
                )
            except ModelNotReadyError:
                pass
        return baseline


class _SageMakerHybridService(BaselineInferenceService):
    """SageMaker for intent + entities, heuristic for bank_category + cca_class."""

    def __init__(self, endpoint: str) -> None:
        from services.ml_inference.providers.sagemaker import SageMakerClassifier

        self._sagemaker = SageMakerClassifier(endpoint)
        self._cache: dict | None = None

    def _call_sagemaker(self, message: dict) -> dict:
        if self._cache is None:
            self._cache = self._sagemaker.invoke(message)
        return self._cache

    def classify_intent(self, text: str, source: str) -> ClassificationResult:
        # Intent comes from SageMaker — but we need the full message for invoke.
        # classify_intent is called from enrich() which has the message.
        # Fallback to heuristic if SageMaker hasn't been called yet.
        if self._cache is not None:
            return ClassificationResult(
                label=self._cache.get("intent_label"),
                confidence=self._cache.get("intent_confidence"),
            )
        return super().classify_intent(text, source)

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        baseline = super().extract_entities(message, text)
        try:
            result = self._call_sagemaker(message)
            sm_entities = result.get("entities") or {}
            merged = dict(baseline.entities)
            for key, value in sm_entities.items():
                if value is not None and value != "" and value != [] and value != {}:
                    merged[key] = value
            return EntityExtractionResult(
                amount=sm_entities.get("amount") if sm_entities.get("amount") is not None else baseline.amount,
                vendor=sm_entities.get("vendor") or baseline.vendor,
                asset_name=sm_entities.get("asset_name") or baseline.asset_name,
                entities=merged,
            )
        except Exception:
            return baseline

    def enrich(self, message: dict) -> dict:
        self._cache = None
        try:
            self._cache = self._sagemaker.invoke(message)
        except Exception:
            pass
        return super().enrich(message)


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

    if provider == "sagemaker":
        from services.ml_inference.providers.sagemaker import SageMakerClassifier

        endpoint = settings.SAGEMAKER_ENDPOINT_NAME
        if not endpoint:
            raise ValueError("SAGEMAKER_ENDPOINT_NAME is required when ML_INFERENCE_PROVIDER=sagemaker")
        return _SageMakerHybridService(endpoint=endpoint)

    raise ValueError(f"unsupported ML inference provider {provider!r}")


@lru_cache
def get_inference_service():
    return build_inference_service()


def enrich_message(message: dict) -> dict:
    return get_inference_service().enrich(message)
