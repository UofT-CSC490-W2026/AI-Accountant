from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from services.shared.transaction_persistence import (
    coerce_transaction_date,
    ensure_transaction_for_message,
)


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


# ── coerce_transaction_date gap tests (lines 23, 27-29) ──────────────────


def test_coerce_transaction_date_returns_date_object_unchanged():
    """Line 23: when value is already a date, return it directly."""
    d = date(2026, 3, 15)
    assert coerce_transaction_date(d) is d


def test_coerce_transaction_date_parses_valid_iso_string():
    """Sanity check for the happy-path string branch."""
    assert coerce_transaction_date("2026-03-15") == date(2026, 3, 15)


def test_coerce_transaction_date_falls_back_on_invalid_string():
    """Lines 27-29: invalid string triggers ValueError, falls through to date.today()."""
    result = coerce_transaction_date("not-a-date")
    assert result == date.today()


def test_coerce_transaction_date_falls_back_on_non_string_non_date():
    """Line 29: non-str, non-date value falls through to date.today()."""
    result = coerce_transaction_date(12345)
    assert result == date.today()


# ── ensure_transaction_for_message insert path (line 46) ──────────────────


def test_pipeline_persistence_inserts_new_transaction_when_no_transaction_id(monkeypatch) -> None:
    """Line 46: when transaction_id is absent, TransactionDAO.insert is called."""
    db = FakeDB()
    user = SimpleNamespace(id=uuid4())
    new_transaction = SimpleNamespace(id=uuid4())
    inserted: dict = {}
    enrichment: dict = {}

    monkeypatch.setattr(
        "services.shared.transaction_persistence.resolve_local_user",
        lambda _db, _external_user_id: user,
    )
    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.get_by_id",
        staticmethod(lambda _db, _tid: (_ for _ in ()).throw(AssertionError("get_by_id should not be called"))),
    )

    def fake_insert(db, user_id, **kwargs):
        inserted["user_id"] = user_id
        inserted.update(kwargs)
        return new_transaction

    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.insert",
        staticmethod(fake_insert),
    )
    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.update_normalized_fields",
        staticmethod(lambda *a, **kw: (_ for _ in ()).throw(AssertionError("update should not be called"))),
    )

    def fake_update_ml_enrichment(_db, transaction_id, intent_label, entities, bank_category, cca_class_match):
        enrichment["transaction_id"] = transaction_id

    monkeypatch.setattr(
        "services.shared.transaction_persistence.TransactionDAO.update_ml_enrichment",
        staticmethod(fake_update_ml_enrichment),
    )

    resolved_user, resolved_transaction = ensure_transaction_for_message(
        db,
        {
            "input_text": "Bought office supplies for 50",
            "source": "manual",
            "currency": "CAD",
            "user_id": "demo-user-1",
        },
    )

    assert resolved_user.id == user.id
    assert resolved_transaction.id == new_transaction.id
    assert inserted["user_id"] == user.id
    assert enrichment["transaction_id"] == new_transaction.id
