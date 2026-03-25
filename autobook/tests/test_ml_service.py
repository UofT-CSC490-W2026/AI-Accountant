from __future__ import annotations

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
    enriched = enrich_message(
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
