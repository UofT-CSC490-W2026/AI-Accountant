from __future__ import annotations

from services.agent import process as agent_process


def test_agent_routes_high_confidence_ml_output_to_posting(monkeypatch) -> None:
    enqueued: list[tuple[str, dict]] = []
    published: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        agent_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )
    monkeypatch.setattr(
        agent_process,
        "publish_sync",
        lambda channel, payload: published.append((channel, payload)),
    )

    agent_process.process(
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
            "entities": {
                "amount": 2400.0,
                "vendor": "Apple",
                "asset_name": "laptop",
                "date": "2026-03-22",
            },
            "confidence": {"ml": 0.97},
        }
    )

    assert published == []
    assert len(enqueued) == 1
    _, payload = enqueued[0]
    assert payload["clarification"]["required"] is False
    assert payload["confidence"]["overall"] == 0.97
    assert payload["proposed_entry"]["lines"] == [
        {
            "account_code": "1500",
            "account_name": "Equipment",
            "type": "debit",
            "amount": 2400.0,
            "line_order": 0,
        },
        {
            "account_code": "1000",
            "account_name": "Cash",
            "type": "credit",
            "amount": 2400.0,
            "line_order": 1,
        },
    ]


def test_agent_routes_ambiguous_transfer_to_clarification_with_rule_engine_output(monkeypatch) -> None:
    enqueued: list[tuple[str, dict]] = []
    published: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        agent_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )
    monkeypatch.setattr(
        agent_process,
        "publish_sync",
        lambda channel, payload: published.append((channel, payload)),
    )

    agent_process.process(
        {
            "parse_id": "parse_agent_2",
            "input_text": "Transferred money to savings",
            "transaction_id": "txn-2",
            "transaction_date": "2026-03-22",
            "amount": 1500.0,
            "source": "manual_text",
            "intent_label": "transfer",
            "bank_category": "transfer",
            "entities": {
                "amount": 1500.0,
                "transfer_destination": "Savings",
                "date": "2026-03-22",
            },
            "confidence": {"ml": 0.82},
        }
    )

    assert len(published) == 1
    assert published[0][0] == "clarification.created"
    assert len(enqueued) == 1
    _, payload = enqueued[0]
    assert payload["clarification"]["required"] is True
    assert payload["clarification"]["reason"] == "Transfer destination account is not confidently mapped."
    assert payload["proposed_entry"]["lines"] == [
        {
            "account_code": "9999",
            "account_name": "Unknown Destination",
            "type": "debit",
            "amount": 1500.0,
            "line_order": 0,
        },
        {
            "account_code": "1000",
            "account_name": "Cash",
            "type": "credit",
            "amount": 1500.0,
            "line_order": 1,
        },
    ]
