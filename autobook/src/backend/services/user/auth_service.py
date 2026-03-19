from __future__ import annotations

import secrets

from fastapi import HTTPException, status

from backend.db.base import AuthRepository
from backend.models.user_model import UserModel
from backend.schema.auth import MessageResponse, TokenResponse
from backend.services.user import password_service, token_service, user_service


INVALID_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid email or password.",
)


def login(
    db: AuthRepository,
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> TokenResponse:
    user = user_service.get_by_email(db, email)
    if not user:
        raise INVALID_CREDENTIALS_ERROR
    if user_service.is_login_locked(user):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Account is temporarily locked.")
    user_service.ensure_account_active(user)
    if not password_service.verify_password(password, user.password_hash):
        user_service.record_login_failure(db, user)
        user_service.write_audit_event(
            db,
            event_type="login_failed",
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise INVALID_CREDENTIALS_ERROR

    user = user_service.record_login_success(db, user)
    token, expires_in = token_service.create_access_token(
        user_id=user.id,
        role=user.role,
        token_version=user.token_version,
    )
    user_service.write_audit_event(
        db,
        event_type="login_succeeded",
        actor_user_id=user.id,
        target_user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


def logout() -> MessageResponse:
    return MessageResponse(message="Logged out on client. Existing access tokens remain valid until expiry.")


def change_password(
    db: AuthRepository,
    *,
    current_user: UserModel,
    current_password: str,
    new_password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MessageResponse:
    if not password_service.verify_password(current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")
    new_hash = password_service.hash_password(new_password)
    user_service.update_password(db, current_user, new_hash)
    user_service.write_audit_event(
        db,
        event_type="password_changed",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return MessageResponse(message="Password updated.")


def issue_password_reset(
    db: AuthRepository,
    *,
    email: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str | None:
    user = user_service.get_by_email(db, email)
    if not user:
        return None
    if user.is_disabled or not user_service.can_issue_reset(user):
        return None
    raw_token = secrets.token_urlsafe(32)
    user_service.create_reset_token_record(db, user, raw_token)
    user_service.write_audit_event(
        db,
        event_type="password_reset_requested",
        target_user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return raw_token


def forgot_password(
    db: AuthRepository,
    *,
    email: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MessageResponse:
    issue_password_reset(db, email=email, ip_address=ip_address, user_agent=user_agent)
    return MessageResponse(message="If the account exists, a password reset link has been issued.")


def reset_password(
    db: AuthRepository,
    *,
    token: str,
    new_password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> MessageResponse:
    user = user_service.get_by_reset_token(db, token)
    if not user or not user.reset_token_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid.")
    if user.reset_token_expires_at <= user_service.utc_now():
        user_service.clear_reset_token(db, user)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired.")
    new_hash = password_service.hash_password(new_password)
    user_service.update_password(db, user, new_hash)
    user_service.write_audit_event(
        db,
        event_type="password_reset_completed",
        target_user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return MessageResponse(message="Password reset successful.")
