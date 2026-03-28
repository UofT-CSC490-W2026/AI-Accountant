from __future__ import annotations

from datetime import date

from db.dao.journal_entries import JournalEntryDAO
from db.dao.users import UserDAO


def _make_user(db):
    return UserDAO.create(db, email=f"je-extra-{id(db)}@example.com")


def test_je_insert_no_lines(db_session):
    import pytest
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="at least one line"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "empty", "status": "draft"},
            [],
        )


def test_je_insert_invalid_type(db_session):
    import pytest
    user = _make_user(db_session)
    with pytest.raises(ValueError, match="invalid type"):
        JournalEntryDAO.insert_with_lines(
            db_session, user.id,
            {"date": date(2026, 3, 23), "description": "bad type", "status": "draft"},
            [{"account_code": "1000", "account_name": "Cash", "type": "wrong", "amount": 100}],
        )
