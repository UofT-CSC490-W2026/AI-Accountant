from __future__ import annotations

import re

from sqlalchemy.orm import Session

from db.dao.users import UserDAO
from db.models.user import User

DEFAULT_EXTERNAL_USER_ID = "demo-user-1"
PLACEHOLDER_PASSWORD_HASH = "cognito-pending"


def normalize_external_user_id(external_user_id: str | None) -> str:
    value = (external_user_id or "").strip()
    return value or DEFAULT_EXTERNAL_USER_ID


def build_local_user_email(external_user_id: str | None) -> str:
    normalized = normalize_external_user_id(external_user_id).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-") or "demo-user"
    return f"{slug}@autobook.local"


def resolve_local_user(db: Session, external_user_id: str | None) -> User:
    email = build_local_user_email(external_user_id)
    user = UserDAO.get_by_email(db, email)
    if user is not None:
        return user
    return UserDAO.create(db, email=email, password_hash=PLACEHOLDER_PASSWORD_HASH)
