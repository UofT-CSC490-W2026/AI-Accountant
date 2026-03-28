from __future__ import annotations

from services.ml_inference.logic import HybridInferenceService
from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult


class FakeClassifier:
    is_ready = True

    def predict_intent(self, text, source):
        return ClassificationResult("asset_purchase", 0.99)

    def predict_bank_category(self, text, intent_label):
        return ClassificationResult("equipment", 0.98)

    def predict_cca_class(self, intent_label, asset_name):
        return ClassificationResult("class_50", 0.95)


class FakeExtractor:
    is_ready = True

    def extract_entities(self, message, text):
        return EntityExtractionResult(
            amount=500.0,
            vendor="Apple",
            asset_name="printer",
            entities={"vendor": "Apple", "asset_name": "printer"},
        )


def test_hybrid_uses_ready_classifier():
    svc = HybridInferenceService(sequence_classifier=FakeClassifier(), entity_extractor=None)
    result = svc.classify_intent("bought printer", "manual")
    assert result.label == "asset_purchase"
    assert result.confidence == 0.99


def test_hybrid_uses_ready_bank_category():
    svc = HybridInferenceService(sequence_classifier=FakeClassifier(), entity_extractor=None)
    result = svc.classify_bank_transaction("bought printer", "asset_purchase")
    assert result.label == "equipment"


def test_hybrid_uses_ready_cca():
    svc = HybridInferenceService(sequence_classifier=FakeClassifier(), entity_extractor=None)
    result = svc.match_cca_class("asset_purchase", "printer")
    assert result.label == "class_50"


def test_hybrid_uses_ready_extractor():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=FakeExtractor())
    result = svc.extract_entities({"input_text": "bought printer from Apple for $500"}, "bought printer from apple for $500")
    assert result.vendor == "Apple"
    assert result.asset_name == "printer"


def test_hybrid_merges_extractor_entities():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=FakeExtractor())
    result = svc.extract_entities({"input_text": "bought printer"}, "bought printer")
    assert "vendor" in result.entities
