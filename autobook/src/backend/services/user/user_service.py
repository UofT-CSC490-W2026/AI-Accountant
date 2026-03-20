from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

from backend.db.base import AuthRepository
from backend.models.user_model import AuditEvent, UserModel
from backend.schema.auth import TokenPayload
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


def sync_cognito_user(
    db: AuthRepository,
    *,
    claims: TokenPayload,
    role: UserRole,
) -> UserModel:
    user = get_by_id(db, claims.sub)
    if user is None:
        user = UserModel(
            id=claims.sub,
            email=_resolve_email(claims),
            full_name=_resolve_full_name(claims),
            role=role,
        )
        return db.add_user(user)

    user.role = role
    if claims.email is not None:
        user.email = normalize_email(claims.email)
    elif user.email is None:
        user.email = _resolve_email(claims)
    full_name = _resolve_full_name(claims)
    if full_name:
        user.full_name = full_name
    return save_user(db, user)


def update_user_profile(db: AuthRepository, user: UserModel, update: UserUpdateRequest) -> UserModel:
    if update.email is not None and normalize_email(update.email) != (user.email or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is managed by Cognito and cannot be changed here.",
        )
    if update.full_name is not None:
        user.full_name = update.full_name.strip() or None
    return save_user(db, user)


def record_authentication(db: AuthRepository, user: UserModel) -> UserModel:
    user.last_authenticated_at = utc_now()
    return save_user(db, user)


def ensure_account_active(user: UserModel) -> None:
    if user.is_disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not verified.")
    if user.is_suspicious:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is pending review.")


def verify_user(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_verified = True
    return save_user(db, user)


def clear_suspicious_flag(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_suspicious = False
    return save_user(db, user)


def disable_user(db: AuthRepository, user: UserModel) -> UserModel:
    user.is_disabled = True
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


def _resolve_email(claims: TokenPayload) -> str | None:
    if claims.email:
        return normalize_email(claims.email)
    if claims.username and "@" in claims.username:
        return normalize_email(claims.username)
    return None


def _resolve_full_name(claims: TokenPayload) -> str | None:
    if claims.name is None:
        return None
    return claims.name.strip() or None
