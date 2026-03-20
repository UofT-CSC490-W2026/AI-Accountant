from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi.testclient import TestClient
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend.config import get_settings
from backend.db.session import get_auth_db, reset_auth_db_for_tests
from backend.main import app
from backend.schema.user import UserRole
from backend.services.user import token_service, user_service

REGION = "us-east-1"
USER_POOL_ID = "us-east-1_testpool"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
KEY_ID = "test-key-id"
PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url_uint(value: int) -> str:
    length = max(1, (value.bit_length() + 7) // 8)
    raw = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


PUBLIC_NUMBERS = PRIVATE_KEY.public_key().public_numbers()
JWKS = {
    "keys": [
        {
            "kty": "RSA",
            "kid": KEY_ID,
            "use": "sig",
            "alg": "RS256",
            "n": _b64url_uint(PUBLIC_NUMBERS.n),
            "e": _b64url_uint(PUBLIC_NUMBERS.e),
        }
    ]
}


@pytest.fixture(autouse=True)
def reset_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("COGNITO_POOL_ID", USER_POOL_ID)
    monkeypatch.setenv("COGNITO_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("AUTOBOOK_COGNITO_JWKS_JSON", json.dumps(JWKS))
    get_settings.cache_clear()
    token_service.clear_caches()
    reset_auth_db_for_tests()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _issue_token(
    *,
    sub: str,
    token_use: str = "access",
    email: str | None = None,
    groups: list[str] | None = None,
    custom_role: str | None = None,
    issuer: str = ISSUER,
    client_id: str = CLIENT_ID,
    expires_delta: timedelta = timedelta(minutes=15),
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": sub,
        "iss": issuer,
        "token_use": token_use,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "cognito:groups": groups or [],
    }
    if token_use == "access":
        payload["client_id"] = client_id
    else:
        payload["aud"] = client_id
    if email is not None:
        payload["email"] = email
        payload["cognito:username"] = email
    if custom_role is not None:
        payload["custom:role"] = custom_role
    header = {"alg": "RS256", "kid": KEY_ID, "typ": "JWT"}
    header_segment = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    payload_segment = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature = PRIVATE_KEY.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    signature_segment = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def test_me_returns_existing_user_for_valid_cognito_token(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None

    token = _issue_token(sub=user.id, groups=[UserRole.REGULAR.value])
    response = client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == "user@example.com"
    assert body["role"] == UserRole.REGULAR.value
    assert body["token_use"] == "access"


def test_me_syncs_new_user_from_cognito_id_token(client: TestClient) -> None:
    token = _issue_token(
        sub="new-cognito-user",
        token_use="id",
        email="new.user@example.com",
        custom_role=UserRole.MANAGER.value,
    )

    response = client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == "new-cognito-user"
    assert body["email"] == "new.user@example.com"
    assert body["role"] == UserRole.MANAGER.value


def test_custom_role_claim_overrides_group_role(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None

    token = _issue_token(
        sub=user.id,
        groups=[UserRole.REGULAR.value],
        custom_role=UserRole.SUPERUSER.value,
    )
    response = client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["role"] == UserRole.SUPERUSER.value


def test_unknown_role_claims_fall_back_to_regular(client: TestClient) -> None:
    token = _issue_token(
        sub="fallback-role-user",
        email="fallback@example.com",
        groups=["finance-team"],
    )
    response = client.get("/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["role"] == UserRole.REGULAR.value


def test_logout_reports_cognito_client_flow(client: TestClient) -> None:
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert "Cognito client flow" in response.json()["message"]


def test_manager_route_requires_role_claims(client: TestClient) -> None:
    db = get_auth_db()
    target_user = user_service.get_by_email(db, "user@example.com")
    manager_user = user_service.get_by_email(db, "manager@example.com")
    assert target_user is not None
    assert manager_user is not None

    regular_token = _issue_token(sub=target_user.id, groups=[UserRole.REGULAR.value])
    regular_response = client.post(f"/auth/users/{target_user.id}/verify", headers=_auth_headers(regular_token))
    assert regular_response.status_code == 403, regular_response.text

    manager_token = _issue_token(sub=manager_user.id, groups=[UserRole.MANAGER.value])
    manager_response = client.post(f"/auth/users/{target_user.id}/verify", headers=_auth_headers(manager_token))
    assert manager_response.status_code == 200, manager_response.text


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Missing bearer token."


def test_me_rejects_malformed_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers=_auth_headers("not-a-jwt"))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Malformed access token."


def test_me_rejects_tampered_signature(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    token = _issue_token(sub=user.id, groups=[UserRole.REGULAR.value])
    header_segment, payload_segment, _signature = token.split(".")
    tampered = f"{header_segment}.{payload_segment}.tampered-signature"

    response = client.get("/auth/me", headers=_auth_headers(tampered))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Invalid token signature."


def test_me_rejects_expired_token(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    token = _issue_token(
        sub=user.id,
        groups=[UserRole.REGULAR.value],
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Token has expired."


def test_me_rejects_wrong_issuer(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    token = _issue_token(
        sub=user.id,
        groups=[UserRole.REGULAR.value],
        issuer="https://example.com/not-cognito",
    )

    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Unexpected token issuer."


def test_me_rejects_wrong_client_id(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    token = _issue_token(
        sub=user.id,
        groups=[UserRole.REGULAR.value],
        client_id="wrong-client-id",
    )

    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Unexpected Cognito app client."
