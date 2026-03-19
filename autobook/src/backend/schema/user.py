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
    email: str
    full_name: str | None = None
    role: UserRole
    is_verified: bool
    is_suspicious: bool
    is_disabled: bool


class MeResponse(UserSummary):
    last_login_at: datetime | None = None
    password_changed_at: datetime
    token_version: int = Field(..., ge=1)


class UserUpdateRequest(BaseModel):
    email: str | None = None
    full_name: str | None = None


class UpdateUserRoleRequest(BaseModel):
    role: UserRole
