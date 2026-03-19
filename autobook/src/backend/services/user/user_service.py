from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from backend.config import get_settings
from backend.db.base import AuthRepository
from backend.models.user_model import AuditEvent, UserModel
from backend.schema.user import UserRole, UserUpdateRequest


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_by_id(db: AuthRepository, user_id: str) -> UserModel | None:
    return db.get_user_by_id(user_id)


def get_by_email(db: AuthRepository, email: str) -> UserModel | None:
    return db.get_user_by_email(normalize_email(email))


def ensure_user_exists(db: AuthRepository, user_id: str) -> UserModel:
    user = get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def save_user(db: AuthRepository, user: UserModel) -> UserModel:
    user.updated_at = utc_now()
    return db.save_user(user)


def update_user_profile(db: AuthRepository, user: UserModel, update: UserUpdateRequest) -> UserModel:
    if update.email is not None:
        normalized = normalize_email(update.email)
        existing = get_by_email(db, normalized)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use.")
        user.email = normalized
    if update.full_name is not None:
        user.full_name = update.full_name.strip() or None
    return save_user(db, user)


def update_password(db: AuthRepository, user: UserModel, password_hash: str) -> UserModel:
    user.password_hash = password_hash
    user.password_changed_at = utc_now()
    user.token_version += 1
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.reset_token_created_at = None
    user.reset_requested_at = None
    return save_user(db, user)


def record_login_success(db: AuthRepository, user: UserModel) -> UserModel:
    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None
    user.last_login_at = utc_now()
    return save_user(db, user)


def record_login_failure(db: AuthRepository, user: UserModel) -> UserModel:
    settings = get_settings()
    user.failed_login_count += 1
    user.last_failed_login_at = utc_now()
    if user.failed_login_count >= settings.login_max_attempts:
        user.locked_until = utc_now() + timedelta(minutes=settings.login_lockout_minutes)
    return save_user(db, user)


def is_login_locked(user: UserModel) -> bool:
    return user.locked_until is not None and user.locked_until > utc_now()


def ensure_account_active(user: UserModel) -> None:
    if user.is_disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not verified.")
    if user.is_suspicious:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is pending review.")


def create_reset_token_record(db: AuthRepository, user: UserModel, raw_token: str) -> UserModel:
    settings = get_settings()
    user.reset_token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    user.reset_token_created_at = utc_now()
    user.reset_requested_at = user.reset_token_created_at
    user.reset_token_expires_at = user.reset_token_created_at + timedelta(
        minutes=settings.password_reset_token_ttl_minutes
    )
    return save_user(db, user)


def can_issue_reset(user: UserModel) -> bool:
    settings = get_settings()
    if not user.reset_requested_at:
        return True
    return utc_now() - user.reset_requested_at >= timedelta(
        minutes=max(1, 60 // settings.password_reset_max_requests_per_hour)
    )


def get_by_reset_token(db: AuthRepository, raw_token: str) -> UserModel | None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return db.get_user_by_reset_token_hash(token_hash)


def clear_reset_token(db: AuthRepository, user: UserModel) -> UserModel:
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.reset_token_created_at = None
    user.reset_requested_at = None
    return save_user(db, user)


def verify_user(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_verified = True
    return save_user(db, user)


def clear_suspicious_flag(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_suspicious = False
    return save_user(db, user)


def update_role(db: AuthRepository, user: UserModel, role: UserRole) -> UserModel:
    user.role = role
    user.token_version += 1
    return save_user(db, user)


def disable_user(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_disabled = True
    user.token_version += 1
    return save_user(db, user)


def write_audit_event(
    db: AuthRepository,
    *,
    event_type: str,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata or {},
    )
    return db.add_audit_event(event)
