from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from db.connection import get_db, set_current_user_context


def test_get_db_yields_and_closes(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr("db.connection.SessionLocal", lambda: mock_session)

    gen = get_db()
    session = next(gen)
    assert session is mock_session
    try:
        next(gen)
    except StopIteration:
        pass
    mock_session.close.assert_called_once()


def test_get_db_rollback_on_exception(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr("db.connection.SessionLocal", lambda: mock_session)

    gen = get_db()
    next(gen)
    try:
        gen.throw(RuntimeError("boom"))
    except RuntimeError:
        pass
    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()


def test_set_user_context():
    mock_session = MagicMock()
    user_id = uuid4()
    set_current_user_context(mock_session, user_id)
    mock_session.execute.assert_called_once()
