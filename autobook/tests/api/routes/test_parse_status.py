from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import parse as parse_route
from auth.schemas import UserRole


def test_get_parse_status_found(monkeypatch):
    app = FastAPI()
    fake_auth = SimpleNamespace(
        user=SimpleNamespace(id="user-1"),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="default",
    )
    app.dependency_overrides[parse_route.get_current_user] = lambda: fake_auth
    app.include_router(parse_route.router)

    async def fake_load(redis, parse_id):
        return {"parse_id": parse_id, "user_id": "user-1", "status": "processing", "stage": "normalizer", "occurred_at": "2026-03-26T00:00:00Z", "updated_at": "2026-03-26T00:00:00Z"}

    monkeypatch.setattr(parse_route, "load_status", fake_load)

    class FakeRedis:
        pass

    app.state.redis = FakeRedis()
    client = TestClient(app)

    response = client.get("/api/v1/parse/parse_abc123")
    assert response.status_code == 200
    assert response.json()["parse_id"] == "parse_abc123"


def test_get_parse_status_not_found(monkeypatch):
    app = FastAPI()
    fake_auth = SimpleNamespace(
        user=SimpleNamespace(id="user-1"),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="default",
    )
    app.dependency_overrides[parse_route.get_current_user] = lambda: fake_auth
    app.include_router(parse_route.router)

    async def fake_load(redis, parse_id):
        return None

    monkeypatch.setattr(parse_route, "load_status", fake_load)

    class FakeRedis:
        pass

    app.state.redis = FakeRedis()
    client = TestClient(app)

    response = client.get("/api/v1/parse/parse_missing")
    assert response.status_code == 404
