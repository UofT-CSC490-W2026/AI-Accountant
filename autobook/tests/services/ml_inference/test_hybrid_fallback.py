from __future__ import annotations

from services.ml_inference.logic import HybridInferenceService
from services.ml_inference.providers import ModelNotReadyError
from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult


class FailingClassifier:
    is_ready = True

    def predict_intent(self, text, source):
        raise ModelNotReadyError("not loaded")

    def predict_bank_category(self, text, intent_label):
        raise ModelNotReadyError("not loaded")

    def predict_cca_class(self, intent_label, asset_name):
        raise ModelNotReadyError("not loaded")


class FailingExtractor:
    is_ready = True

    def extract_entities(self, message, text):
        raise ModelNotReadyError("not loaded")


def test_hybrid_fallback_intent_on_model_error():
    svc = HybridInferenceService(sequence_classifier=FailingClassifier(), entity_extractor=None)
    result = svc.classify_intent("Bought printer", "manual")
    assert result.label == "asset_purchase"


def test_hybrid_fallback_bank_on_model_error():
    svc = HybridInferenceService(sequence_classifier=FailingClassifier(), entity_extractor=None)
    result = svc.classify_bank_transaction("test", "transfer")
    assert result.label == "transfer"


def test_hybrid_fallback_cca_on_model_error():
    svc = HybridInferenceService(sequence_classifier=FailingClassifier(), entity_extractor=None)
    result = svc.match_cca_class("asset_purchase", "laptop")
    assert result.label == "class_50"


def test_hybrid_fallback_entities_on_model_error():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=FailingExtractor())
    result = svc.extract_entities({"input_text": "bought printer"}, "bought printer")
    assert isinstance(result, EntityExtractionResult)
