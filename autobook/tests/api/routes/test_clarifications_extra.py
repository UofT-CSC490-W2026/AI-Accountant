from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import clarifications as cl_routes
from auth.deps import get_current_user, require_role, get_db
from auth.schemas import UserRole


def _fake_auth(role=UserRole.MANAGER):
    return SimpleNamespace(
        user=SimpleNamespace(id=uuid.UUID("11111111-1111-1111-1111-111111111111")),
        claims=SimpleNamespace(token_use="access"),
        role=role,
        role_source="cognito:groups",
    )


def _make_client(monkeypatch, tasks=None, resolve_result=None):
    app = FastAPI()
    app.include_router(cl_routes.router)
    auth = _fake_auth()
    app.dependency_overrides[get_current_user] = lambda: auth
    app.dependency_overrides[require_role(UserRole.MANAGER)] = lambda: auth
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(commit=lambda: None, rollback=lambda: None)

    if tasks is not None:
        monkeypatch.setattr(cl_routes.ClarificationDAO, "list_pending", staticmethod(lambda _db, _uid: tasks))
    if resolve_result is not None:
        monkeypatch.setattr(cl_routes.ClarificationDAO, "resolve", staticmethod(lambda _db, _tid, action, edited_entry=None: resolve_result))
    monkeypatch.setattr(cl_routes.pub, "clarification_resolved", lambda **kw: None)

    return TestClient(app)


def test_clarifications_resolve_not_found_returns_404(monkeypatch):
    client = _make_client(monkeypatch, resolve_result=(None, None))
    response = client.post(
        f"/api/v1/clarifications/{uuid.uuid4()}/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 404


def test_clarifications_resolve_invalid_uuid_returns_404(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.post(
        "/api/v1/clarifications/not-a-uuid/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 404
