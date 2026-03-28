from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import auth as auth_route
from auth.schemas import UserRole
from config import get_settings


def create_client() -> TestClient:
    app = FastAPI()
    fake_auth_context = SimpleNamespace(
        user=SimpleNamespace(
            id="user-auth-1",
            cognito_sub="cognito-sub-1",
            email="user@example.com",
        ),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="cognito:groups",
    )
    app.dependency_overrides[auth_route.get_current_user] = lambda: fake_auth_context
    app.include_router(auth_route.router)
    return TestClient(app)


def test_auth_login_url_builds_cognito_hosted_ui_url(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_DOMAIN", "autobook-dev.auth.ca-central-1.amazoncognito.com")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-123")

    client = create_client()
    response = client.get(
        "/api/v1/auth/login-url",
        params={
            "redirect_uri": "http://localhost:5173/auth/callback",
            "code_challenge": "challenge-123",
            "state": "state-123",
        },
    )

    assert response.status_code == 200
    login_url = response.json()["hosted_ui_url"]
    assert login_url.startswith("https://autobook-dev.auth.ca-central-1.amazoncognito.com/login?")
    assert "client_id=client-123" in login_url
    assert "code_challenge=challenge-123" in login_url
    assert "state=state-123" in login_url


def test_auth_signup_url_builds_cognito_hosted_ui_url(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_DOMAIN", "autobook-dev.auth.ca-central-1.amazoncognito.com")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-123")

    client = create_client()
    response = client.get(
        "/api/v1/auth/signup-url",
        params={
            "redirect_uri": "http://localhost:5173/auth/callback",
            "code_challenge": "challenge-123",
            "state": "state-123",
        },
    )

    assert response.status_code == 200
    signup_url = response.json()["hosted_ui_url"]
    assert signup_url.startswith("https://autobook-dev.auth.ca-central-1.amazoncognito.com/signup?")
    assert "client_id=client-123" in signup_url
    assert "code_challenge=challenge-123" in signup_url
    assert "state=state-123" in signup_url


def test_auth_logout_url_builds_cognito_logout_url(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_DOMAIN", "autobook-dev.auth.ca-central-1.amazoncognito.com")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "client-123")

    client = create_client()
    response = client.get(
        "/api/v1/auth/logout-url",
        params={"logout_uri": "http://localhost:5173/login"},
    )

    assert response.status_code == 200
    assert response.json()["logout_url"].startswith(
        "https://autobook-dev.auth.ca-central-1.amazoncognito.com/logout?"
    )


def test_auth_token_exchange_returns_backend_payload(monkeypatch):
    client = create_client()

    async def fake_exchange(form_data: dict[str, str]):
        assert form_data["grant_type"] == "authorization_code"
        return {
            "access_token": "access-123",
            "refresh_token": "refresh-123",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

    monkeypatch.setattr(auth_route, "_exchange_token", fake_exchange)

    response = client.post(
        "/api/v1/auth/token",
        json={
            "code": "code-123",
            "redirect_uri": "http://localhost:5173/auth/callback",
            "code_verifier": "verifier-123",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-123"
    assert response.json()["refresh_token"] == "refresh-123"


def test_auth_validate_returns_authenticated_user():
    client = create_client()
    response = client.get("/api/v1/auth/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "user@example.com"
