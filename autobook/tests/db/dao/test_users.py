from __future__ import annotations

from uuid import uuid4

from db.dao.users import UserDAO


def test_users_create(db_session):
    user = UserDAO.create(db_session, email="test@example.com", password_hash="hash123")
    assert user.email == "test@example.com"
    assert user.id is not None


def test_users_get_by_id_found(db_session):
    user = UserDAO.create(db_session, email="found@example.com")
    result = UserDAO.get_by_id(db_session, user.id)
    assert result is not None
    assert result.id == user.id


def test_users_get_by_id_not_found(db_session):
    result = UserDAO.get_by_id(db_session, uuid4())
    assert result is None


def test_users_get_by_email(db_session):
    user = UserDAO.create(db_session, email="email@example.com")
    result = UserDAO.get_by_email(db_session, "email@example.com")
    assert result is not None
    assert result.id == user.id


def test_users_get_by_cognito_sub(db_session):
    user = UserDAO.create(db_session, email="cog@example.com", cognito_sub="sub-123")
    result = UserDAO.get_by_cognito_sub(db_session, "sub-123")
    assert result is not None
    assert result.id == user.id


def test_users_get_or_create_new(db_session):
    user = UserDAO.get_or_create_from_cognito_claims(db_session, "new-sub", "new@example.com")
    assert user.email == "new@example.com"
    assert user.cognito_sub == "new-sub"


def test_users_get_or_create_existing(db_session):
    user1 = UserDAO.get_or_create_from_cognito_claims(db_session, "exist-sub", "exist@example.com")
    user2 = UserDAO.get_or_create_from_cognito_claims(db_session, "exist-sub", "exist@example.com")
    assert user1.id == user2.id


def test_users_get_or_create_updates_email(db_session):
    user1 = UserDAO.get_or_create_from_cognito_claims(db_session, "update-sub", "old@example.com")
    user2 = UserDAO.get_or_create_from_cognito_claims(db_session, "update-sub", "new@example.com")
    assert user1.id == user2.id
    assert user2.email == "new@example.com"
