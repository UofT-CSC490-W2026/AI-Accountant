from __future__ import annotations

from datetime import datetime, timezone

from db.dao.auth_sessions import AuthSessionDAO
from db.dao.users import UserDAO


def _make_user(db):
    return UserDAO.create(db, email=f"auth-{id(db)}@example.com")


def test_auth_sessions_create(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    session = AuthSessionDAO.record_token(
        db_session, user, "sub-1", "token-abc", "access", now, now,
    )
    assert session.id is not None
    assert session.cognito_sub == "sub-1"


def test_auth_sessions_update_seen(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    s1 = AuthSessionDAO.record_token(db_session, user, "sub-1", "token-xyz", "access", now, now)
    s2 = AuthSessionDAO.record_token(db_session, user, "sub-1", "token-xyz", "access", now, now)
    assert s1.id == s2.id
    assert s2.last_seen_at is not None


def test_auth_sessions_update_user(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    AuthSessionDAO.record_token(db_session, user, "sub-1", "token-user", "access", now, now)
    assert user.last_authenticated_at is not None
