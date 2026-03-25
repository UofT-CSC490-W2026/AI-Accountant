from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services.normalizer.service import NormalizationService
from services.shared.transaction_persistence import ensure_transaction_for_message
from services.normalizer import process as normalizer_process


class FakeDB:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_normalization_service_marks_ambiguous_amounts_as_not_confident() -> None:
    service = NormalizationService()

    normalized = service.normalize(
        {
            "input_text": "Paid invoice 100 and tax 13 on 03/22/2026",
            "source": "manual",
            "currency": "CAD",
        }
    )

    assert normalized.amount is None
    assert normalized.amount_confident is False
    assert normalized.transaction_date == "2026-03-22"
    assert normalized.normalized_description == "paid invoice 100 and tax 13 on 03/22/2026"
    assert [mention["value"] for mention in normalized.amount_mentions] == [100.0, 13.0]
    assert normalized.party_mentions == []


def test_normalization_service_extracts_clear_manual_amount_and_counterparty() -> None:
    service = NormalizationService()

    normalized = service.normalize(
        {
            "input_text": "Bought a laptop from Apple for $2400",
            "source": "manual",
            "currency": "CAD",
        }
    )

    assert normalized.source == "manual_text"
    assert normalized.amount == 2400.0
    assert normalized.amount_confident is True
    assert normalized.counterparty == "Apple"
    assert normalized.normalized_description == "bought a laptop from apple for $2400"


def test_normalizer_persists_canonical_transaction_before_enqueue(monkeypatch) -> None:
    db = FakeDB()
    user = SimpleNamespace(id=uuid4())
    transaction = SimpleNamespace(id=uuid4())
    inserted: dict = {}
    enqueued: list[tuple[str, dict]] = []

    monkeypatch.setattr(normalizer_process, "SessionLocal", lambda: db)
    monkeypatch.setattr(normalizer_process, "resolve_local_user", lambda _db, _external_user_id: user)

    def fake_insert(**kwargs):
        inserted.update(kwargs)
        return transaction

    monkeypatch.setattr(normalizer_process.TransactionDAO, "insert", staticmethod(fake_insert))
    monkeypatch.setattr(
        normalizer_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )

    normalizer_process.process(
        {
            "parse_id": "parse_normalizer_1",
            "input_text": "Bought a laptop from Apple for $2400",
            "user_id": "demo-user-1",
            "source": "manual",
            "currency": "CAD",
        }
    )

    assert inserted["user_id"] == user.id
    assert inserted["normalized_description"] == "bought a laptop from apple for $2400"
    assert inserted["amount"] == 2400.0
    assert inserted["counterparty"] == "Apple"
    assert inserted["amount_mentions"] == [{"text": "$2400", "value": 2400.0}]
    assert inserted["party_mentions"] == [{"text": "Apple", "value": "Apple"}]
    assert db.committed is True
    assert enqueued[0][1]["transaction_id"] == str(transaction.id)
    assert enqueued[0][1]["normalized_description"] == inserted["normalized_description"]
    assert enqueued[0][1]["amount_mentions"] == inserted["amount_mentions"]
    assert enqueued[0][1]["source"] == "manual_text"


def test_pipeline_persistence_updates_existing_transaction_instead_of_reinserting(monkeypatch) -> None:
    db = FakeDB()
    user = SimpleNamespace(id=uuid4())
    existing_transaction = SimpleNamespace(id=uuid4())
    updated: dict = {}
    enrichment: dict = {}

    monkeypatch.setattr("services.shared.transaction_persistence.resolve_local_user", lambda _db, _external_user_id: user)
    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.get_by_id",
        staticmethod(lambda _db, transaction_id: existing_transaction if str(transaction_id) == str(existing_transaction.id) else None),
    )
    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.insert",
        staticmethod(lambda **_kwargs: (_ for _ in ()).throw(AssertionError("insert should not be called"))),
    )

    def fake_update_normalized_fields(_db, transaction_id, **kwargs):
        updated["transaction_id"] = transaction_id
        updated.update(kwargs)
        return existing_transaction

    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.update_normalized_fields",
        staticmethod(fake_update_normalized_fields),
    )

    def fake_update_ml_enrichment(_db, transaction_id, intent_label, entities, bank_category, cca_class_match):
        enrichment["transaction_id"] = transaction_id
        enrichment["intent_label"] = intent_label
        enrichment["entities"] = entities
        enrichment["bank_category"] = bank_category
        enrichment["cca_class_match"] = cca_class_match
        return existing_transaction

    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.update_ml_enrichment",
        staticmethod(fake_update_ml_enrichment),
    )

    resolved_user, resolved_transaction = ensure_transaction_for_message(
        db,
        {
            "transaction_id": str(existing_transaction.id),
            "input_text": "Paid Slack subscription for 39",
            "source": "manual",
            "currency": "CAD",
            "user_id": "demo-user-1",
            "intent_label": "software_subscription",
            "entities": {"amount": 39.0},
            "bank_category": "software_subscription",
            "cca_class_match": None,
        },
    )

    assert resolved_user.id == user.id
    assert resolved_transaction.id == existing_transaction.id
    assert updated["transaction_id"] == existing_transaction.id
    assert updated["normalized_description"] == "paid slack subscription for 39"
    assert updated["amount"] == 39.0
    assert updated["amount_mentions"] == [{"text": "39", "value": 39.0}]
    assert enrichment["transaction_id"] == existing_transaction.id
    assert enrichment["intent_label"] == "software_subscription"
