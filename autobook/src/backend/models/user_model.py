from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.schema.user import UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UserModel:
    id: str
    email: str | None = None
    role: UserRole = UserRole.REGULAR
    full_name: str | None = None
    identity_provider: str = "cognito"
    is_verified: bool = True
    is_suspicious: bool = False
    is_disabled: bool = False
    last_authenticated_at: datetime | None = None
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
