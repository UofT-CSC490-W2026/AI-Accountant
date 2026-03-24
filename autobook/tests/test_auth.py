from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Some backend modules create the SQLAlchemy engine at import time.
# Provide a harmless local default so auth tests can collect without a live DB.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from auth import deps as auth_deps
from auth import token_service
from config import get_settings
import api.main as api_main
import api.routes.clarifications as clarifications_routes
import api.routes.parse as parse_routes
from auth.mock_cognito import MockCognito, MockCognitoConfig


MOCK_COGNITO = MockCognito(
    MockCognitoConfig(
        region="us-east-1",
        user_pool_id="us-east-1_testpool",
        client_id="test-client-id",
        key_id="test-key-id",
    )
)


class DummyRedis:
    async def aclose(self) -> None:
        return None


@dataclass
class DummyUser:
    id: uuid.UUID
    cognito_sub: str
    email: str


@pytest.fixture(autouse=True)
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in MOCK_COGNITO.env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    token_service.clear_caches()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    user = DummyUser(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        cognito_sub="cognito-user-1",
        email="user@example.com",
    )
    enqueued: list[dict[str, object]] = []

    async def fake_get_redis(_url: str) -> DummyRedis:
        return DummyRedis()

    def fake_user_lookup(_db, cognito_sub: str, email: str | None) -> DummyUser:
        resolved_email = email or user.email
        return DummyUser(id=user.id, cognito_sub=cognito_sub, email=resolved_email)

    def fake_db():
        yield SimpleNamespace(commit=lambda: None, rollback=lambda: None)

    def fake_enqueue(_queue_url: str, payload: dict) -> str:
        enqueued.append(payload)
        return "queued"

    def fake_publish_sync(_channel: str, _payload: dict) -> None:
        return None

    def fake_resolve(_db, _clarification_id, action: str, edited_entry=None):
        if action == "reject":
            status = "rejected"
            journal_entry = None
        else:
            status = "resolved"
            journal_entry = SimpleNamespace(id=uuid.UUID("22222222-2222-2222-2222-222222222222"))

        task = SimpleNamespace(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            user_id=user.id,
            status=status,
            source_text="Need clarification",
            explanation="manager review",
            confidence=0.5,
            proposed_entry={"lines": []},
        )
        return task, journal_entry

    monkeypatch.setattr(api_main, "get_redis", fake_get_redis)
    monkeypatch.setattr(auth_deps.UserDAO, "get_or_create_from_cognito_claims", staticmethod(fake_user_lookup))
    monkeypatch.setattr(parse_routes, "enqueue", fake_enqueue)
    monkeypatch.setattr(clarifications_routes, "publish_sync", fake_publish_sync)
    monkeypatch.setattr(clarifications_routes.ClarificationDAO, "resolve", staticmethod(fake_resolve))
    api_main.app.dependency_overrides[auth_deps.get_db] = fake_db
    api_main.app.state._test_enqueued = enqueued

    with TestClient(api_main.app) as test_client:
        yield test_client

    api_main.app.dependency_overrides.clear()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_me_accepts_valid_cognito_token(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
    )

    response = client.get("/api/v1/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cognito_sub"] == "cognito-user-1"
    assert body["email"] == "user@example.com"
    assert body["role"] == "regular"
    assert body["role_source"] == "cognito:groups"
    assert body["token_use"] == "access"


def test_auth_me_accepts_access_tokens_with_at_jwt_header_type(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
        header_alg="ES256",
        header_typ="at+jwt",
    )

    response = client.get("/api/v1/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["email"] == "user@example.com"


def test_auth_me_accepts_demo_token_when_demo_mode_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_DEMO_MODE", "true")
    get_settings.cache_clear()

    response = client.get("/api/v1/auth/me", headers=_auth_headers("demo:teammate@example.com"))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cognito_sub"] == "demo:teammate@example.com"
    assert body["email"] == "teammate@example.com"
    assert body["role"] == "regular"


def test_private_route_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/ledger")
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Missing bearer token."


def test_parse_uses_authenticated_user_id_not_request_user_id(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
    )

    response = client.post(
        "/api/v1/parse",
        headers=_auth_headers(token),
        json={
            "input_text": "Bought office chairs",
            "source": "manual",
            "currency": "CAD",
            "user_id": "attacker-controlled-id",
        },
    )

    assert response.status_code == 200, response.text
    enqueued = client.app.state._test_enqueued
    assert enqueued[-1]["user_id"] == "11111111-1111-1111-1111-111111111111"


def test_auth_me_rejects_expired_token(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Token has expired."


def test_auth_me_rejects_wrong_client_id(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
        client_id="wrong-client-id",
    )

    response = client.get("/api/v1/auth/me", headers=_auth_headers(token))
    assert response.status_code == 401, response.text
    assert response.json()["detail"] == "Unexpected Cognito app client."


def test_manager_role_can_resolve_clarification(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-manager-1",
        email="manager@example.com",
        groups=["manager"],
    )

    response = client.post(
        "/api/v1/clarifications/33333333-3333-3333-3333-333333333333/resolve",
        headers=_auth_headers(token),
        json={"action": "approve"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"


def test_regular_role_cannot_resolve_clarification(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        groups=["regular"],
    )

    response = client.post(
        "/api/v1/clarifications/33333333-3333-3333-3333-333333333333/resolve",
        headers=_auth_headers(token),
        json={"action": "approve"},
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "manager role required."


def test_custom_role_used_as_fallback_when_groups_missing(client: TestClient) -> None:
    token = MOCK_COGNITO.issue_token(
        sub="cognito-user-1",
        email="user@example.com",
        custom_role="superuser",
    )

    response = client.get("/api/v1/auth/me", headers=_auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "superuser"
    assert body["role_source"] == "custom:role"
