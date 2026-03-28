from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from db.dao.journal_entries import JournalEntryDAO
from db.dao.users import UserDAO


def _make_user(db):
    return UserDAO.create(db, email=f"je-{id(db)}@example.com")


def _post_entry(db, user, entry_date=None, description="Test entry", amount=500):
    entry_date = entry_date or date(2026, 3, 23)
    return JournalEntryDAO.insert_with_lines(
        db, user.id,
        {"date": entry_date, "description": description, "status": "posted"},
        [
            {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": amount},
            {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
        ],
    )


def test_je_insert_no_lines(db_session):
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="at least one line"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "Empty", "status": "draft"},
            [],
        )


def test_je_insert_invalid_type(db_session):
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="invalid type"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "Bad type", "status": "draft"},
            [{"account_code": "1000", "type": "invalid", "amount": 100}],
        )


def test_je_insert_negative_amount(db_session):
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="positive"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "Negative", "status": "draft"},
            [{"account_code": "1000", "type": "debit", "amount": -100}],
        )


def test_je_insert_auto_creates_unknown_account(db_session):
    user = _make_user(db_session)
    entry = JournalEntryDAO.insert_with_lines(
        db_session, user.id,
        {"date": date(2026, 3, 23), "description": "Auto-create acct", "status": "draft"},
        [
            {"account_code": "9999", "account_name": "New Account", "type": "debit", "amount": 100},
            {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 100},
        ],
    )
    assert entry is not None
    from db.dao.chart_of_accounts import ChartOfAccountsDAO
    created = ChartOfAccountsDAO.get_by_code(db_session, user.id, "9999")
    assert created is not None
    assert created.auto_created is True


def test_je_insert_unbalanced(db_session):
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="does not balance"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "Bad entry", "status": "draft"},
            [
                {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 500},
                {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 300},
            ],
        )


def test_je_insert_with_lines(db_session):
    user = _make_user(db_session)
    entry = _post_entry(db_session, user)
    assert entry.id is not None
    assert entry.status == "posted"
    assert len(entry.lines) == 2


def test_je_list_date_filter(db_session):
    user = _make_user(db_session)
    _post_entry(db_session, user, entry_date=date(2026, 1, 1), description="Jan")
    _post_entry(db_session, user, entry_date=date(2026, 6, 1), description="Jun")
    results = JournalEntryDAO.list_by_user(
        db_session, user.id, filters={"date_from": date(2026, 3, 1)},
    )
    assert len(results) == 1
    assert results[0].description == "Jun"


def test_je_list_account_filter(db_session):
    user = _make_user(db_session)
    _post_entry(db_session, user)
    results = JournalEntryDAO.list_by_user(
        db_session, user.id, filters={"account": "1500"},
    )
    assert len(results) == 1


def test_je_get_by_id(db_session):
    user = _make_user(db_session)
    entry = _post_entry(db_session, user)
    result = JournalEntryDAO.get_by_id(db_session, entry.id)
    assert result is not None
    assert result.id == entry.id
    assert len(result.lines) == 2


def test_je_compute_balances(db_session):
    user = _make_user(db_session)
    _post_entry(db_session, user, amount=1000)
    balances = JournalEntryDAO.compute_balances(db_session, user.id)
    assert len(balances) >= 2
    equipment = next(b for b in balances if b["account_code"] == "1500")
    assert equipment["balance"] == Decimal("1000")


def test_je_compute_summary(db_session):
    user = _make_user(db_session)
    _post_entry(db_session, user, amount=750)
    summary = JournalEntryDAO.compute_summary(db_session, user.id)
    assert summary["total_debits"] == Decimal("750")
    assert summary["total_credits"] == Decimal("750")
