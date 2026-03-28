from __future__ import annotations

from db.dao.users import UserDAO


def test_users_get_or_create_updates_email(db_session):
    user1 = UserDAO.get_or_create_from_cognito_claims(db_session, "sub-1", "old@example.com")
    user2 = UserDAO.get_or_create_from_cognito_claims(db_session, "sub-1", "new@example.com")
    assert user1.id == user2.id
    assert user2.email == "new@example.com"
