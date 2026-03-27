"""Tests for SageMaker inference provider and _SageMakerHybridService."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ml_inference.logic import _SageMakerHybridService, build_inference_service
from services.ml_inference.providers.sagemaker import SageMakerClassifier


# ── Fixtures ─────────────────────────────────────────────────────────────

SAMPLE_SAGEMAKER_RESPONSE = {
    "intent_label": "asset_purchase",
    "intent_confidence": 0.777,
    "entities": {
        "vendor": None,
        "asset_name": None,
        "amount": 2400.0,
        "transfer_destination": None,
        "mentioned_date": None,
    },
}

SAMPLE_MESSAGE = {
    "parse_id": "parse_sm_1",
    "input_text": "Bought a laptop from Apple for $2400",
    "source": "manual_text",
    "transaction_date": "2026-03-26",
    "counterparty": "Apple",
    "amount_mentions": [{"text": "$2400", "value": 2400.0}],
    "date_mentions": [],
    "party_mentions": [{"text": "Apple", "value": "Apple"}],
    "quantity_mentions": [],
    "entities": {},
    "user_id": "user-1",
    "currency": "CAD",
}


def _mock_invoke_endpoint(response_body: dict):
    """Create a mock boto3 sagemaker-runtime client."""
    mock_client = MagicMock()
    mock_client.invoke_endpoint.return_value = {
        "Body": MagicMock(read=lambda: json.dumps(response_body).encode())
    }
    return mock_client


# ── SageMakerClassifier ─────────────────────────────────────────────────

def test_sagemaker_classifier_invoke():
    mock_client = _mock_invoke_endpoint(SAMPLE_SAGEMAKER_RESPONSE)
    with patch("services.ml_inference.providers.sagemaker.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        classifier = SageMakerClassifier("test-endpoint")

    classifier._client = mock_client
    result = classifier.invoke(SAMPLE_MESSAGE)

    assert result["intent_label"] == "asset_purchase"
    assert result["intent_confidence"] == 0.777
    assert result["entities"]["amount"] == 2400.0
    mock_client.invoke_endpoint.assert_called_once()
    call_kwargs = mock_client.invoke_endpoint.call_args[1]
    assert call_kwargs["EndpointName"] == "test-endpoint"
    assert call_kwargs["ContentType"] == "application/json"


def test_sagemaker_classifier_classify_intent():
    mock_client = _mock_invoke_endpoint(SAMPLE_SAGEMAKER_RESPONSE)
    with patch("services.ml_inference.providers.sagemaker.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        classifier = SageMakerClassifier("test-endpoint")

    classifier._client = mock_client
    result = classifier.classify_intent(SAMPLE_MESSAGE)

    assert result.label == "asset_purchase"
    assert result.confidence == 0.777


def test_sagemaker_classifier_extract_entities():
    mock_client = _mock_invoke_endpoint(SAMPLE_SAGEMAKER_RESPONSE)
    with patch("services.ml_inference.providers.sagemaker.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        classifier = SageMakerClassifier("test-endpoint")

    classifier._client = mock_client
    result = classifier.extract_entities(SAMPLE_MESSAGE)

    assert result.amount == 2400.0
    assert result.vendor is None
    assert result.asset_name is None


# ── _SageMakerHybridService ─────────────────────────────────────────────

def _make_hybrid_service(sagemaker_response: dict) -> _SageMakerHybridService:
    """Create a hybrid service with a mocked SageMaker classifier."""
    mock_client = _mock_invoke_endpoint(sagemaker_response)
    with patch("services.ml_inference.providers.sagemaker.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        service = _SageMakerHybridService(endpoint="test-endpoint")
    service._sagemaker._client = mock_client
    return service


def test_hybrid_enrich_uses_sagemaker_intent():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    result = service.enrich(SAMPLE_MESSAGE)

    assert result["intent_label"] == "asset_purchase"
    assert result["confidence"]["ml"] > 0


def test_hybrid_enrich_heuristic_bank_category():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    result = service.enrich(SAMPLE_MESSAGE)

    # bank_category comes from heuristic, not SageMaker
    assert result["bank_category"] == "equipment"


def test_hybrid_enrich_heuristic_cca_class():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    result = service.enrich(SAMPLE_MESSAGE)

    # cca_class_match comes from heuristic, not SageMaker
    assert result["cca_class_match"] == "class_50"


def test_hybrid_enrich_merges_sagemaker_entities():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    result = service.enrich(SAMPLE_MESSAGE)

    # SageMaker returned amount=2400, vendor=None
    # Heuristic should fill vendor from party_mentions
    assert result["entities"]["amount"] == 2400.0


def test_hybrid_enrich_sagemaker_entity_overrides_heuristic():
    response = {
        **SAMPLE_SAGEMAKER_RESPONSE,
        "entities": {
            "vendor": "Apple Inc",
            "asset_name": "laptop",
            "amount": 2400.0,
            "transfer_destination": None,
            "mentioned_date": None,
        },
    }
    service = _make_hybrid_service(response)
    result = service.enrich(SAMPLE_MESSAGE)

    # SageMaker returned non-null vendor — should override heuristic
    assert result["entities"]["vendor"] == "Apple Inc"
    assert result["entities"]["asset_name"] == "laptop"


def test_hybrid_enrich_falls_back_on_sagemaker_failure():
    """When SageMaker fails, full heuristic pipeline runs."""
    mock_client = MagicMock()
    mock_client.invoke_endpoint.side_effect = Exception("endpoint down")
    with patch("services.ml_inference.providers.sagemaker.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        service = _SageMakerHybridService(endpoint="test-endpoint")
    service._sagemaker._client = mock_client

    result = service.enrich(SAMPLE_MESSAGE)

    # Should still work via heuristic fallback
    assert result["intent_label"] == "asset_purchase"
    assert result["bank_category"] == "equipment"


def test_hybrid_classify_intent_uses_cache():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    # Pre-populate cache via enrich
    service.enrich(SAMPLE_MESSAGE)

    # classify_intent should use cached SageMaker result
    result = service.classify_intent("ignored text", "ignored source")
    assert result.label == "asset_purchase"
    assert result.confidence == 0.777


def test_hybrid_classify_intent_heuristic_without_cache():
    service = _make_hybrid_service(SAMPLE_SAGEMAKER_RESPONSE)
    # Don't call enrich — cache is empty

    # Should fall back to heuristic
    result = service.classify_intent("Bought a laptop from Apple for $2400", "manual_text")
    assert result.label == "asset_purchase"
    # Confidence from heuristic, not SageMaker
    assert result.confidence == 0.95


# ── build_inference_service ──────────────────────────────────────────────

def test_build_sagemaker_service(monkeypatch):
    monkeypatch.setenv("SAGEMAKER_ENDPOINT_NAME", "test-endpoint")
    monkeypatch.setenv("ML_INFERENCE_PROVIDER", "sagemaker")

    from config import get_settings
    get_settings.cache_clear()
    try:
        with patch("services.ml_inference.providers.sagemaker.boto3"):
            service = build_inference_service("sagemaker")
        assert isinstance(service, _SageMakerHybridService)
    finally:
        get_settings.cache_clear()


def test_build_sagemaker_service_missing_endpoint(monkeypatch):
    monkeypatch.delenv("SAGEMAKER_ENDPOINT_NAME", raising=False)

    from config import get_settings
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="SAGEMAKER_ENDPOINT_NAME is required"):
            build_inference_service("sagemaker")
    finally:
        get_settings.cache_clear()


def test_build_unsupported_provider():
    with pytest.raises(ValueError, match="unsupported"):
        build_inference_service("nonexistent")
