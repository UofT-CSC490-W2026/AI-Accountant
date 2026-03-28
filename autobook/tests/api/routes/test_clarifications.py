from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import clarifications as cl_routes
from auth.deps import AuthContext, get_current_user, require_role
from auth.schemas import UserRole
from db.connection import get_db


def _fake_auth(role=UserRole.MANAGER):
    return AuthContext(
        user=SimpleNamespace(id=uuid.UUID("11111111-1111-1111-1111-111111111111")),
        claims=SimpleNamespace(token_use="access"),
        role=role,
        role_source="cognito:groups",
    )


def _make_client(monkeypatch, tasks=None, resolve_result=None, role=UserRole.MANAGER):
    app = FastAPI()
    app.include_router(cl_routes.router)
    auth = _fake_auth(role)
    app.dependency_overrides[get_current_user] = lambda: auth
    app.dependency_overrides[require_role(UserRole.MANAGER)] = lambda: auth
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(commit=lambda: None, rollback=lambda: None)

    if tasks is not None:
        monkeypatch.setattr(cl_routes.ClarificationDAO, "list_pending", staticmethod(lambda _db, _uid: tasks))
    if resolve_result is not None:
        monkeypatch.setattr(cl_routes.ClarificationDAO, "resolve", staticmethod(lambda _db, _tid, action, edited_entry=None: resolve_result))
    monkeypatch.setattr(cl_routes.pub, "clarification_resolved", lambda **kw: None)

    return TestClient(app)


def _make_task(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "status": "pending",
        "source_text": "test input",
        "explanation": "needs review",
        "confidence": Decimal("0.5"),
        "proposed_entry": {"entry": {}, "lines": []},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_clarifications_list(monkeypatch):
    task = _make_task()
    client = _make_client(monkeypatch, tasks=[task])
    response = client.get("/api/v1/clarifications")
    assert response.status_code == 200
    assert response.json()["count"] == 1


def test_clarifications_empty(monkeypatch):
    client = _make_client(monkeypatch, tasks=[])
    response = client.get("/api/v1/clarifications")
    assert response.status_code == 200
    assert response.json()["count"] == 0
    assert response.json()["items"] == []


def test_clarifications_resolve_approve(monkeypatch):
    task = _make_task(status="resolved")
    je = SimpleNamespace(id=uuid.uuid4())
    client = _make_client(monkeypatch, resolve_result=(task, je))
    response = client.post(
        f"/api/v1/clarifications/{task.id}/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_clarifications_resolve_reject(monkeypatch):
    task = _make_task(status="rejected")
    client = _make_client(monkeypatch, resolve_result=(task, None))
    response = client.post(
        f"/api/v1/clarifications/{task.id}/resolve",
        json={"action": "reject"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["journal_entry_id"] is None


def test_clarifications_resolve_edit(monkeypatch):
    task = _make_task(status="resolved")
    je = SimpleNamespace(id=uuid.uuid4())
    client = _make_client(monkeypatch, resolve_result=(task, je))
    response = client.post(
        f"/api/v1/clarifications/{task.id}/resolve",
        json={
            "action": "edit",
            "edited_entry": {
                "entry": {"date": "2026-03-23", "description": "Edited"},
                "lines": [
                    {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 500},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 500},
                ],
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_clarifications_resolve_not_found(monkeypatch):
    client = _make_client(monkeypatch, resolve_result=(None, None))
    response = client.post(
        "/api/v1/clarifications/11111111-1111-1111-1111-111111111111/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 404


def test_clarifications_resolve_invalid_uuid(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.post(
        "/api/v1/clarifications/not-a-uuid/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 404


def test_clarifications_resolve_forbidden(monkeypatch):
    app = FastAPI()
    app.include_router(cl_routes.router)
    auth = _fake_auth(role=UserRole.REGULAR)
    app.dependency_overrides[get_current_user] = lambda: auth
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()
    monkeypatch.setattr(cl_routes.pub, "clarification_resolved", lambda **kw: None)
    client = TestClient(app)

    response = client.post(
        "/api/v1/clarifications/11111111-1111-1111-1111-111111111111/resolve",
        json={"action": "approve"},
    )
    assert response.status_code == 403
