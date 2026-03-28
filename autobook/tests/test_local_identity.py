from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from local_identity import (
    DEFAULT_EXTERNAL_USER_ID,
    build_local_user_email,
    normalize_external_user_id,
    resolve_local_user,
)


def test_normalize_with_value():
    assert normalize_external_user_id("user-123") == "user-123"
    assert normalize_external_user_id("  spaced  ") == "spaced"


def test_normalize_defaults():
    assert normalize_external_user_id(None) == DEFAULT_EXTERNAL_USER_ID
    assert normalize_external_user_id("") == DEFAULT_EXTERNAL_USER_ID
    assert normalize_external_user_id("   ") == DEFAULT_EXTERNAL_USER_ID


def test_build_email():
    assert build_local_user_email("user-123") == "user-123@autobook.local"
    assert build_local_user_email("John.Doe+test") == "john-doe-test@autobook.local"
    assert build_local_user_email(None) == "demo-user-1@autobook.local"


def test_resolve_existing():
    existing = MagicMock()
    db = MagicMock()
    with patch("local_identity.UserDAO") as mock_dao:
        mock_dao.get_by_email.return_value = existing
        result = resolve_local_user(db, "user-123")
    assert result is existing
    mock_dao.get_by_email.assert_called_once_with(db, "user-123@autobook.local")
    mock_dao.create.assert_not_called()


def test_resolve_creates_new():
    new_user = MagicMock()
    db = MagicMock()
    with patch("local_identity.UserDAO") as mock_dao:
        mock_dao.get_by_email.return_value = None
        mock_dao.create.return_value = new_user
        result = resolve_local_user(db, "user-123")
    assert result is new_user
    mock_dao.create.assert_called_once_with(
        db, email="user-123@autobook.local", password_hash="cognito-pending"
    )


def test_resolve_uses_real_user_id_when_present():
    existing = MagicMock()
    db = MagicMock()
    user_id = uuid.uuid4()

    with patch("local_identity.UserDAO") as mock_dao:
        mock_dao.get_by_id.return_value = existing
        result = resolve_local_user(db, str(user_id))

    assert result is existing
    mock_dao.get_by_id.assert_called_once_with(db, user_id)
    mock_dao.get_by_email.assert_not_called()
    mock_dao.create.assert_not_called()
