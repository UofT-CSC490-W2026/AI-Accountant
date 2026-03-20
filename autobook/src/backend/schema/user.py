from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    REGULAR = "regular"
    MANAGER = "manager"
    SUPERUSER = "superuser"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None = None
    full_name: str | None = None
    role: UserRole
    identity_provider: str
    is_verified: bool
    is_suspicious: bool
    is_disabled: bool


class MeResponse(UserSummary):
    last_authenticated_at: datetime | None = None
    token_use: str
    cognito_groups: list[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    email: str | None = None
    full_name: str | None = None
