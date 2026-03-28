from __future__ import annotations

from types import SimpleNamespace

import services.ml_inference.service as service_module
import services.shared.transaction_persistence as transaction_persistence
from services.ml_inference.schemas import EntityExtractionResult
from services.ml_inference.service import (
    BaselineInferenceService,
    HybridInferenceService,
    build_inference_service,
    enrich_message,
)


def test_service_prefers_explicit_vendor_pattern() -> None:
    service = BaselineInferenceService()

    result = service.extract_entities(
        {
            "transaction_date": "2026-03-22",
            "amount_mentions": [{"text": "$2400", "value": 2400.0}],
            "party_mentions": [{"text": "Apple", "value": "Apple"}],
            "quantity_mentions": [{"text": "1 laptop", "value": 1, "unit": "laptop"}],
        },
        "Bought a laptop from Apple for $2400",
    )

    assert result.vendor == "Apple"
    assert result.amount == 2400.0
    assert result.asset_name == "laptop"
    assert result.entities["vendor"] == "Apple"


def test_service_amount_extraction_ignores_date_tokens() -> None:
    service = BaselineInferenceService()

    result = service.extract_entities(
        {"transaction_date": "2026-03-22"},
        "Paid rent on 2026-03-22 for 1800",
    )

    assert result.amount == 1800.0
    assert result.entities["mentioned_date"] == "2026-03-22"


def test_service_extracts_transfer_destination() -> None:
    service = BaselineInferenceService()

    result = service.extract_entities(
        {"transaction_date": "2026-03-22"},
        "Transferred money to savings",
    )

    assert result.entities["transfer_destination"] == "Savings"


def test_service_prefers_normalizer_mentions_over_reparsing() -> None:
    service = BaselineInferenceService()

    result = service.extract_entities(
        {
            "transaction_date": "2026-03-22",
            "amount_mentions": [
                {"text": "$100,000", "value": 100000.0},
                {"text": "$150,000", "value": 150000.0},
            ],
            "party_mentions": [{"text": "Kheela's Hardware", "value": "Kheela'S Hardware"}],
            "quantity_mentions": [{"text": "100 computers", "value": 100, "unit": "computers"}],
        },
        "Purchased 100 computers as inventory from Kheela's Hardware and pay $100,000 cash.",
    )

    assert result.vendor == "Kheela's Hardware"
    assert result.amount is None
    assert result.entities["quantity"] == 100
    assert len(result.entities["amount_mentions"]) == 2


def test_service_classifies_bank_transaction_and_cca_match() -> None:
    service = BaselineInferenceService()

    intent = service.classify_intent("Bought a printer for $500", "manual")
    bank_category = service.classify_bank_transaction("Bought a printer for $500", intent.label)
    cca_match = service.match_cca_class(intent.label, "printer")

    assert intent.label == "asset_purchase"
    assert bank_category.label == "equipment"
    assert cca_match.label == "class_50"
    assert service.score_confidence(intent.confidence, bank_category.confidence, cca_match.confidence) > 0.9


def test_service_classifies_software_subscription_with_vendor_keywords() -> None:
    service = BaselineInferenceService()

    intent = service.classify_intent("Paid Slack subscription for 39", "manual")
    bank_category = service.classify_bank_transaction("Paid Slack subscription for 39", intent.label)

    assert intent.label == "software_subscription"
    assert bank_category.label == "software_subscription"


def test_enrich_message_uses_service_boundary() -> None:
    enriched = build_inference_service("heuristic").enrich(
        {
            "parse_id": "parse_service_1",
            "input_text": "Transferred money",
            "source": "manual",
            "currency": "CAD",
            "user_id": "user-1",
        }
    )

    assert enriched["intent_label"] == "transfer"
    assert enriched["bank_category"] == "transfer"
    assert enriched["cca_class_match"] is None
    assert enriched["confidence"]["ml"] > 0.8
    assert enriched["input_type"] == "manual_text"
    assert enriched["normalized_text"] == "transferred money"


def test_build_inference_service_defaults_to_heuristic() -> None:
    service = build_inference_service("heuristic")

    assert isinstance(service, BaselineInferenceService)


def test_hybrid_service_falls_back_to_heuristics_without_models() -> None:
    service = build_inference_service("hybrid")

    assert isinstance(service, HybridInferenceService)

    enriched = service.enrich(
        {
            "parse_id": "parse_service_2",
            "input_text": "Bought a printer for $500",
            "source": "manual_text",
            "currency": "CAD",
            "user_id": "user-1",
        }
    )

    assert enriched["intent_label"] == "asset_purchase"
    assert enriched["bank_category"] == "equipment"
    assert enriched["cca_class_match"] == "class_50"


def test_hybrid_service_prefers_normalizer_vendor_and_date_over_ner() -> None:
    class FakeExtractor:
        @property
        def is_ready(self) -> bool:
            return True

        def extract_entities(self, _message: dict, _text: str) -> EntityExtractionResult:
            return EntityExtractionResult(
                amount=2400.0,
                vendor="Coffee",
                asset_name="laptop",
                entities={
                    "amount": 2400.0,
                    "vendor": "Coffee",
                    "asset_name": "laptop",
                    "mentioned_date": "-03-14",
                },
            )

    service = HybridInferenceService(entity_extractor=FakeExtractor())

    result = service.extract_entities(
        {
            "counterparty": "Pilot Coffee Roasters",
            "transaction_date": "2026-03-14",
            "amount_mentions": [{"text": "$2400", "value": 2400.0}],
            "date_mentions": [{"text": "2026-03-14", "value": "2026-03-14"}],
            "party_mentions": [{"text": "Pilot Coffee Roasters", "value": "Pilot Coffee Roasters"}],
        },
        "Bought a laptop from Pilot Coffee Roasters on 2026-03-14 for $2400",
    )

    assert result.vendor == "Pilot Coffee Roasters"
    assert result.asset_name == "laptop"
    assert result.entities["vendor"] == "Pilot Coffee Roasters"
    assert result.entities["mentioned_date"] == "2026-03-14"


def test_execute_persists_enriched_transaction_state(monkeypatch) -> None:
    commits: list[str] = []
    persisted_messages: list[dict] = []

    class FakeInferenceService:
        def enrich(self, message: dict) -> dict:
            return {
                **message,
                "amount": 2400.0,
                "counterparty": "Apple",
                "intent_label": "asset_purchase",
                "entities": {"amount": 2400.0, "vendor": "Apple", "asset_name": "laptop"},
                "bank_category": "equipment",
                "cca_class_match": "class_50",
                "confidence": {"ml": 0.82},
            }

    fake_db = SimpleNamespace(
        commit=lambda: commits.append("commit"),
        rollback=lambda: commits.append("rollback"),
        close=lambda: commits.append("close"),
    )

    monkeypatch.setattr(service_module, "get_inference_service", lambda: FakeInferenceService())
    monkeypatch.setattr(service_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        transaction_persistence,
        "ensure_transaction_for_message",
        lambda db, message: (
            persisted_messages.append(message) or True,
            SimpleNamespace(id="txn-persisted"),
        ),
    )

    result = service_module.execute(
        {
            "parse_id": "parse-persist-1",
            "transaction_id": "txn-original",
            "input_text": "Bought a laptop from Apple for $2400",
            "source": "manual_text",
            "currency": "CAD",
            "user_id": "user-1",
            "store": True,
        }
    )

    assert result["transaction_id"] == "txn-persisted"
    assert persisted_messages[0]["intent_label"] == "asset_purchase"
    assert persisted_messages[0]["counterparty"] == "Apple"
    assert commits == ["commit", "close"]
