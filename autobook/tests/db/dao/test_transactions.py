from __future__ import annotations

from datetime import date
from uuid import uuid4

from db.dao.transactions import TransactionDAO
from db.dao.users import UserDAO


def _make_user(db):
    return UserDAO.create(db, email=f"tx-{id(db)}@example.com")


def _insert_tx(db, user):
    return TransactionDAO.insert(
        db=db, user_id=user.id,
        description="Bought printer for $500", normalized_description="bought printer for $500",
        amount=500.0, currency="CAD", date=date(2026, 3, 23),
        source="manual", counterparty="Staples",
    )


def test_transactions_insert(db_session):
    user = _make_user(db_session)
    tx = _insert_tx(db_session, user)
    assert tx.id is not None
    assert tx.description == "Bought printer for $500"
    assert tx.amount == 500.0


def test_transactions_update_normalized(db_session):
    user = _make_user(db_session)
    tx = _insert_tx(db_session, user)
    result = TransactionDAO.update_normalized_fields(
        db_session, tx.id, normalized_description="updated description",
    )
    assert result.normalized_description == "updated description"


def test_transactions_update_ml(db_session):
    user = _make_user(db_session)
    tx = _insert_tx(db_session, user)
    result = TransactionDAO.update_ml_enrichment(
        db_session, tx.id,
        intent_label="asset_purchase", entities={"vendor": "Staples"},
        bank_category="equipment", cca_class_match="class_50",
    )
    assert result.intent_label == "asset_purchase"
    assert result.bank_category == "equipment"


def test_transactions_get_by_id_found(db_session):
    user = _make_user(db_session)
    tx = _insert_tx(db_session, user)
    result = TransactionDAO.get_by_id(db_session, tx.id)
    assert result is not None
    assert result.id == tx.id


def test_transactions_get_by_id_not_found(db_session):
    result = TransactionDAO.get_by_id(db_session, uuid4())
    assert result is None


def test_transactions_update_all_fields(db_session):
    user = _make_user(db_session)
    tx = _insert_tx(db_session, user)
    result = TransactionDAO.update_normalized_fields(
        db_session, tx.id,
        description="Updated desc", normalized_description="updated desc",
        amount=999.0, currency="USD", date=date(2026, 6, 1),
        source="csv_upload", counterparty="New Vendor",
        amount_mentions=[{"text": "$999", "value": 999.0}],
        date_mentions=[{"text": "2026-06-01", "value": "2026-06-01"}],
        party_mentions=[{"text": "New Vendor", "value": "New Vendor"}],
        quantity_mentions=[{"text": "1 item", "value": 1, "unit": "item"}],
    )
    assert result.description == "Updated desc"
    assert result.currency == "USD"
    assert result.counterparty == "New Vendor"


def test_transactions_update_ml_not_found(db_session):
    result = TransactionDAO.update_ml_enrichment(
        db_session, uuid4(),
        intent_label="test", entities=None, bank_category=None, cca_class_match=None,
    )
    assert result is None
