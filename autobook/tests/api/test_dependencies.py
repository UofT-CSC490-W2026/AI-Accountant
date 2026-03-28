from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from api.dependencies import get_current_local_user
from db.connection import get_db


def _make_app():
    app = FastAPI()

    @app.get("/test-user")
    def test_user(user=Depends(get_current_local_user)):
        return {"user_id": str(user.id), "email": user.email}

    return app


def test_get_current_local_user_from_param(monkeypatch):
    fake_user = SimpleNamespace(id="user-123", email="test@autobook.local")
    monkeypatch.setattr("api.dependencies.resolve_local_user", lambda _db, uid: fake_user)

    app = _make_app()
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    client = TestClient(app)

    response = client.get("/test-user?userId=custom-user")
    assert response.status_code == 200
    assert response.json()["user_id"] == "user-123"


def test_get_current_local_user_default(monkeypatch):
    fake_user = SimpleNamespace(id="demo-1", email="demo-user-1@autobook.local")
    calls = []

    def track_resolve(_db, uid):
        calls.append(uid)
        return fake_user

    monkeypatch.setattr("api.dependencies.resolve_local_user", track_resolve)

    app = _make_app()
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    client = TestClient(app)

    response = client.get("/test-user")
    assert response.status_code == 200
    assert calls[0] is None
