from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services.shared.transaction_persistence import ensure_transaction_for_message


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
