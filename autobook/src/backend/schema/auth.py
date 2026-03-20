from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageResponse(BaseModel):
    message: str


class TokenPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    sub: str
    exp: int
    iat: int
    iss: str
    token_use: str
    email: str | None = None
    username: str | None = Field(default=None, alias="cognito:username")
    cognito_groups: list[str] = Field(default_factory=list, alias="cognito:groups")
    custom_role: str | None = Field(default=None, alias="custom:role")
    aud: str | None = None
    client_id: str | None = None
    scope: str | None = None
    name: str | None = None

    @property
    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(self.exp)
