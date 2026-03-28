from __future__ import annotations

import pytest

from services.ml_inference.logic import HybridInferenceService, build_inference_service
from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult


def test_build_inference_service_heuristic():
    svc = build_inference_service("heuristic")
    assert svc is not None


def test_build_inference_service_hybrid():
    svc = build_inference_service("hybrid")
    assert isinstance(svc, HybridInferenceService)


def test_build_inference_service_unknown():
    with pytest.raises(ValueError, match="unsupported"):
        build_inference_service("magical")


def test_hybrid_falls_back_classify_intent():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=None)
    result = svc.classify_intent("Bought printer for $500", "manual")
    assert result.label == "asset_purchase"


def test_hybrid_falls_back_bank_category():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=None)
    result = svc.classify_bank_transaction("test", "transfer")
    assert result.label == "transfer"


def test_hybrid_falls_back_cca_class():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=None)
    result = svc.match_cca_class("asset_purchase", "laptop")
    assert result.label == "class_50"


def test_hybrid_falls_back_extract_entities():
    svc = HybridInferenceService(sequence_classifier=None, entity_extractor=None)
    result = svc.extract_entities({"input_text": "Bought printer"}, "bought printer")
    assert isinstance(result, EntityExtractionResult)
