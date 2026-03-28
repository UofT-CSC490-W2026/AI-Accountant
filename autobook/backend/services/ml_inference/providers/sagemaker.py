"""SageMaker inference provider — calls InvokeEndpoint for intent + NER.

Returns intent_label, intent_confidence, and entities.
bank_category and cca_class_match are NOT served by SageMaker —
HybridInferenceService handles those via heuristic fallback.
"""
from __future__ import annotations

import json
import logging

import boto3

from config import get_settings
from services.ml_inference.schemas import ClassificationResult, EntityExtractionResult

logger = logging.getLogger(__name__)


class SageMakerClassifier:
    """Calls SageMaker endpoint for intent classification + entity extraction."""

    def __init__(self, endpoint_name: str) -> None:
        settings = get_settings()
        self._client = boto3.client(
            "sagemaker-runtime",
            region_name=settings.AWS_REGION or settings.AWS_DEFAULT_REGION,
        )
        self._endpoint = endpoint_name

    def invoke(self, message: dict) -> dict:
        """Call SageMaker endpoint and return raw response dict."""
        text = str(
            message.get("input_text")
            or message.get("description")
            or ""
        )
        payload = {
            "input_text": text,
            "source": message.get("source", "manual_text"),
            "transaction_date": str(message.get("transaction_date", "")),
            "counterparty": message.get("counterparty"),
            "amount_mentions": message.get("amount_mentions") or [],
            "date_mentions": message.get("date_mentions") or [],
            "party_mentions": message.get("party_mentions") or [],
            "quantity_mentions": message.get("quantity_mentions") or [],
            "entities": message.get("entities") or {},
        }
        response = self._client.invoke_endpoint(
            EndpointName=self._endpoint,
            ContentType="application/json",
            Body=json.dumps(payload),
        )
        return json.loads(response["Body"].read())

    def classify_intent(self, message: dict) -> ClassificationResult:
        """Extract intent_label + intent_confidence from SageMaker response."""
        result = self.invoke(message)
        return ClassificationResult(
            label=result.get("intent_label"),
            confidence=result.get("intent_confidence"),
        )

    def extract_entities(self, message: dict) -> EntityExtractionResult:
        """Extract entities from SageMaker response."""
        result = self.invoke(message)
        entities = result.get("entities") or {}
        return EntityExtractionResult(
            amount=entities.get("amount"),
            vendor=entities.get("vendor"),
            asset_name=entities.get("asset_name"),
            entities=entities,
        )
