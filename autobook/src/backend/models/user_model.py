from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.schema.user import UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserModel:
    id: str
    email: str
    password_hash: str
    role: UserRole = UserRole.REGULAR
    full_name: str | None = None
    is_verified: bool = True
    is_suspicious: bool = False
    is_disabled: bool = False
    password_changed_at: datetime = field(default_factory=utc_now)
    token_version: int = 1
    last_login_at: datetime | None = None
    last_failed_login_at: datetime | None = None
    failed_login_count: int = 0
    locked_until: datetime | None = None
    reset_token_hash: str | None = None
    reset_token_expires_at: datetime | None = None
    reset_token_created_at: datetime | None = None
    reset_requested_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class AuditEvent:
    event_type: str
    target_user_id: str | None = None
    actor_user_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
