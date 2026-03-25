from __future__ import annotations

from services.precedent import process as precedent_process
from services.precedent.service import PrecedentCandidate, find_precedent_match


def test_find_precedent_match_detects_exact_repeat_transaction() -> None:
    match = find_precedent_match(
        {
            "normalized_description": "bought a laptop from apple for $2400",
            "amount": 2400.0,
            "counterparty": "Apple",
            "source": "manual_text",
        },
        [
            PrecedentCandidate(
                pattern_id="journal_entry:abc123",
                normalized_description="bought a laptop from apple for $2400",
                amount=2400.0,
                counterparty="Apple",
                source="manual_text",
                lines=[
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
                ],
            )
        ],
    )

    assert match.matched is True
    assert match.pattern_id == "journal_entry:abc123"
    assert match.confidence == 0.99


def test_precedent_process_short_circuits_to_posting_for_strong_match(monkeypatch) -> None:
    enqueued: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        precedent_process,
        "_load_candidates",
        lambda _message: [
            PrecedentCandidate(
                pattern_id="journal_entry:precedent-1",
                normalized_description="bought a laptop from apple for $2400",
                amount=2400.0,
                counterparty="Apple",
                source="manual_text",
                lines=[
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
                ],
            )
        ],
    )
    monkeypatch.setattr(
        precedent_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )

    precedent_process.process(
        {
            "parse_id": "parse_precedent_1",
            "transaction_id": "txn-precedent-1",
            "input_text": "Bought a laptop from Apple for $2400",
            "description": "Bought a laptop from Apple for $2400",
            "normalized_description": "bought a laptop from apple for $2400",
            "transaction_date": "2026-03-22",
            "amount": 2400.0,
            "counterparty": "Apple",
            "source": "manual_text",
        }
    )

    assert len(enqueued) == 1
    _, payload = enqueued[0]
    assert payload["precedent_match"] == {
        "matched": True,
        "pattern_id": "journal_entry:precedent-1",
        "confidence": 0.99,
    }
    assert payload["confidence"]["precedent"] == 0.99
    assert payload["confidence"]["overall"] == 0.99
    assert payload["proposed_entry"]["entry"]["origin_tier"] == 1


def test_precedent_process_falls_through_to_ml_when_match_is_weak(monkeypatch) -> None:
    enqueued: list[tuple[str, dict]] = []

    monkeypatch.setattr(
        precedent_process,
        "_load_candidates",
        lambda _message: [
            PrecedentCandidate(
                pattern_id="journal_entry:weak-1",
                normalized_description="paid annual insurance premium",
                amount=900.0,
                counterparty="Intact",
                source="manual_text",
                lines=[],
            )
        ],
    )
    monkeypatch.setattr(
        precedent_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )

    precedent_process.process(
        {
            "parse_id": "parse_precedent_2",
            "transaction_id": "txn-precedent-2",
            "input_text": "Bought a laptop from Apple for $2400",
            "description": "Bought a laptop from Apple for $2400",
            "normalized_description": "bought a laptop from apple for $2400",
            "transaction_date": "2026-03-22",
            "amount": 2400.0,
            "counterparty": "Apple",
            "source": "manual_text",
        }
    )

    assert len(enqueued) == 1
    _, payload = enqueued[0]
    assert payload["precedent_match"] == {
        "matched": False,
        "pattern_id": None,
        "confidence": None,
    }
    assert payload["confidence"]["precedent"] is None
    assert "proposed_entry" not in payload
