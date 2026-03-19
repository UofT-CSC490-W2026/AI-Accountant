from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., gt=0)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


class TokenPayload(BaseModel):
    sub: str
    exp: int
    iat: int
    jti: str
    token_version: int
    role: str | None = None

    @property
    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(self.exp)
