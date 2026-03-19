from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backend.db.session import get_auth_db, reset_auth_db_for_tests
from backend.main import app
from backend.schema.user import UserRole
from backend.services.user import auth_service, token_service, user_service


@pytest.fixture(autouse=True)
def reset_db() -> None:
    reset_auth_db_for_tests()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_and_me(client: TestClient) -> None:
    token = _login(client, "user@example.com", "RegularPass123!")
    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["role"] == UserRole.REGULAR.value


def test_logout_does_not_revoke_access_token(client: TestClient) -> None:
    token = _login(client, "user@example.com", "RegularPass123!")
    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = client.get("/auth/me", headers=_auth_headers(token))
    assert me_response.status_code == 200, me_response.text


def test_password_reset_invalidates_existing_tokens(client: TestClient) -> None:
    old_token = _login(client, "user@example.com", "RegularPass123!")
    db = get_auth_db()
    reset_token = auth_service.issue_password_reset(db, email="user@example.com")
    assert reset_token is not None

    response = client.post(
        "/auth/reset-password",
        json={"token": reset_token, "new_password": "NewRegularPass123!"},
    )
    assert response.status_code == 200, response.text

    old_token_response = client.get("/auth/me", headers=_auth_headers(old_token))
    assert old_token_response.status_code == 401, old_token_response.text

    new_token = _login(client, "user@example.com", "NewRegularPass123!")
    me_response = client.get("/auth/me", headers=_auth_headers(new_token))
    assert me_response.status_code == 200, me_response.text


def test_superuser_role_change_invalidates_old_manager_token(client: TestClient) -> None:
    superuser_token = _login(client, "admin@example.com", "SuperuserPass123!")
    manager_token = _login(client, "manager@example.com", "ManagerPass123!")
    db = get_auth_db()
    manager = user_service.get_by_email(db, "manager@example.com")
    assert manager is not None

    response = client.patch(
        f"/auth/users/{manager.id}/role",
        json={"role": "regular"},
        headers=_auth_headers(superuser_token),
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == UserRole.REGULAR.value

    old_manager_token_response = client.post(
        f"/auth/users/{manager.id}/clear-suspicious",
        headers=_auth_headers(manager_token),
    )
    assert old_manager_token_response.status_code == 401, old_manager_token_response.text


def test_me_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Missing bearer token."


def test_me_rejects_malformed_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers=_auth_headers("not-a-jwt"))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Malformed access token."


def test_me_rejects_tampered_signature(client: TestClient) -> None:
    token = _login(client, "user@example.com", "RegularPass123!")
    header_segment, payload_segment, _signature = token.split(".")
    tampered = f"{header_segment}.{payload_segment}.tampered-signature"

    response = client.get("/auth/me", headers=_auth_headers(tampered))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Invalid token signature."


def test_me_rejects_expired_token(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    token, _expires_in = token_service.create_access_token(
        user_id=user.id,
        role=user.role,
        token_version=user.token_version,
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get("/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Token has expired."


def test_me_rejects_unexpected_algorithm_header(client: TestClient) -> None:
    db = get_auth_db()
    user = user_service.get_by_email(db, "user@example.com")
    assert user is not None
    valid_token, _expires_in = token_service.create_access_token(
        user_id=user.id,
        role=user.role,
        token_version=user.token_version,
    )
    _header_segment, payload_segment, _signature_segment = valid_token.split(".")

    forged_header = token_service._b64url_encode(
        json.dumps({"alg": "HS512", "typ": "JWT"}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{forged_header}.{payload_segment}".encode("ascii")
    forged_signature = token_service._sign(signing_input)
    forged_token = f"{forged_header}.{payload_segment}.{forged_signature}"

    response = client.get("/auth/me", headers=_auth_headers(forged_token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Unexpected token algorithm."
