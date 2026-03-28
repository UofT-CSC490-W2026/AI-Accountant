from __future__ import annotations

from accounting_engine.rules import build_rule_based_entry


def test_agent_routes_high_confidence_ml_output_to_posting() -> None:
    result = build_rule_based_entry(
        {
            "parse_id": "parse_agent_1",
            "input_text": "Bought a laptop from Apple for $2400",
            "transaction_id": "txn-1",
            "transaction_date": "2026-03-22",
            "amount": 2400.0,
            "counterparty": "Apple",
            "source": "manual_text",
            "intent_label": "asset_purchase",
            "bank_category": "equipment",
            "entities": {"amount": 2400.0, "vendor": "Apple", "asset_name": "laptop"},
        },
        confidence=0.97,
        origin_tier=2,
    )

    assert not result.requires_human_review
    lines = result.proposed_entry["lines"]
    assert lines[0]["account_name"] == "Equipment"
    assert lines[0]["type"] == "debit"
    assert lines[0]["amount"] == 2400.0
    assert lines[1]["account_name"] == "Cash"
    assert lines[1]["type"] == "credit"
    assert lines[1]["amount"] == 2400.0


def test_agent_routes_ambiguous_transfer_to_clarification_with_rule_engine_output() -> None:
    result = build_rule_based_entry(
        {
            "parse_id": "parse_agent_2",
            "input_text": "Transferred money to savings",
            "transaction_id": "txn-2",
            "transaction_date": "2026-03-22",
            "amount": 1500.0,
            "source": "manual_text",
            "intent_label": "transfer",
            "bank_category": "transfer",
            "entities": {"amount": 1500.0, "transfer_destination": "Savings"},
        },
        confidence=0.82,
        origin_tier=2,
    )

    assert result.requires_human_review
    assert result.clarification_reason == "Transfer destination account is not confidently mapped."
    lines = result.proposed_entry["lines"]
    assert lines[0]["account_name"] == "Unknown Destination"
    assert lines[0]["type"] == "debit"
    assert lines[0]["amount"] == 1500.0
    assert lines[1]["account_name"] == "Cash"
    assert lines[1]["type"] == "credit"
    assert lines[1]["amount"] == 1500.0
