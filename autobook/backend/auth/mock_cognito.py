from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _b64url_uint(value: int) -> str:
    length = max(1, (value.bit_length() + 7) // 8)
    raw = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_json(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class MockCognitoConfig:
    region: str = "us-east-1"
    user_pool_id: str = "us-east-1_mockpool"
    client_id: str = "mock-client-id"
    key_id: str = "mock-key-id"

    @property
    def issuer(self) -> str:
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"


class MockCognito:
    def __init__(self, config: MockCognitoConfig | None = None) -> None:
        self.config = config or MockCognitoConfig()
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @property
    def env_vars(self) -> dict[str, str]:
        public_numbers = self._private_key.public_key().public_numbers()
        jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": self.config.key_id,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64url_uint(public_numbers.n),
                    "e": _b64url_uint(public_numbers.e),
                }
            ]
        }
        return {
            "AWS_REGION": self.config.region,
            "COGNITO_USER_POOL_ID": self.config.user_pool_id,
            "COGNITO_CLIENT_ID": self.config.client_id,
            "COGNITO_JWKS_JSON": json.dumps(jwks),
        }

    def issue_token(
        self,
        *,
        sub: str,
        token_use: str = "access",
        email: str | None = None,
        name: str | None = None,
        groups: list[str] | None = None,
        custom_role: str | None = None,
        issuer: str | None = None,
        client_id: str | None = None,
        expires_delta: timedelta = timedelta(minutes=15),
    ) -> str:
        now = datetime.now(timezone.utc)
        resolved_issuer = issuer or self.config.issuer
        resolved_client_id = client_id or self.config.client_id
        payload: dict[str, object] = {
            "sub": sub,
            "iss": resolved_issuer,
            "token_use": token_use,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
            "cognito:groups": groups or [],
        }
        if token_use == "access":
            payload["client_id"] = resolved_client_id
        else:
            payload["aud"] = resolved_client_id
        if email is not None:
            payload["email"] = email
            payload["cognito:username"] = email
        if name is not None:
            payload["name"] = name
        if custom_role is not None:
            payload["custom:role"] = custom_role

        header_segment = _b64url_json({"alg": "RS256", "kid": self.config.key_id, "typ": "JWT"})
        payload_segment = _b64url_json(payload)
        signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
        signature = self._private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        signature_segment = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
        return f"{header_segment}.{payload_segment}.{signature_segment}"

    def sample_tokens(self) -> dict[str, str]:
        return {
            "regular_access_token": self.issue_token(
                sub="mock-regular-user",
                email="regular@example.com",
                groups=["regular"],
                name="Mock Regular",
            ),
            "regular_id_token": self.issue_token(
                sub="mock-id-user",
                token_use="id",
                email="iduser@example.com",
                groups=["regular"],
                name="Mock Id User",
            ),
            "manager_access_token": self.issue_token(
                sub="mock-manager-user",
                email="manager@example.com",
                groups=["manager"],
                name="Mock Manager",
            ),
            "superuser_access_token": self.issue_token(
                sub="mock-superuser-user",
                email="superuser@example.com",
                groups=["superuser"],
                name="Mock Superuser",
            ),
        }
