from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.config import get_settings
from backend.schema.auth import TokenPayload
from backend.schema.user import UserRole


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _sign(message: bytes) -> str:
    settings = get_settings()
    digest = hmac.new(settings.secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def create_access_token(*, user_id: str, role: UserRole, token_version: int, expires_delta: timedelta | None = None) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int(expires.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid4()),
        "token_version": token_version,
        "role": role.value,
    }
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature_segment = _sign(signing_input)
    return f"{header_segment}.{payload_segment}.{signature_segment}", int((expires - now).total_seconds())


def decode_access_token(token: str) -> TokenPayload:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise ValueError("Malformed access token.") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise ValueError("Invalid token signature.")

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Invalid token encoding.") from exc

    settings = get_settings()
    if header.get("alg") != settings.jwt_algorithm:
        raise ValueError("Unexpected token algorithm.")

    token_payload = TokenPayload.model_validate(payload)
    now = int(datetime.now(timezone.utc).timestamp())
    if token_payload.exp <= now:
        raise ValueError("Token has expired.")
    return token_payload
