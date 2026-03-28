from __future__ import annotations

import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import statements as stmt_route
from auth.deps import AuthContext, get_current_user
from auth.schemas import UserRole
from db.connection import get_db


def _make_client(monkeypatch):
    app = FastAPI()
    app.include_router(stmt_route.router)

    auth = AuthContext(
        user=SimpleNamespace(id=uuid.UUID("11111111-1111-1111-1111-111111111111")),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="cognito:groups",
    )
    app.dependency_overrides[get_current_user] = lambda: auth
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()

    default_result = {
        "statement_type": "balance_sheet",
        "period": {"as_of": "2026-03-23"},
        "sections": [],
        "totals": {"total_assets": 0.0, "total_liabilities": 0.0, "total_equity": 0.0},
    }

    monkeypatch.setattr(stmt_route, "build_balance_sheet", lambda _db, _uid, _as_of: default_result)
    monkeypatch.setattr(stmt_route, "build_income_statement", lambda _db, _uid, _as_of: {
        "statement_type": "income_statement",
        "period": {"as_of": "2026-03-23"},
        "sections": [],
        "totals": {"total_revenue": 0.0, "total_expenses": 0.0, "net_income": 0.0},
    })
    monkeypatch.setattr(stmt_route, "build_trial_balance", lambda _db, _uid, _as_of: {
        "statement_type": "trial_balance",
        "period": {"as_of": "2026-03-23"},
        "sections": [],
        "totals": {"total_debits": 0.0, "total_credits": 0.0},
    })

    return TestClient(app)


def test_statements_balance_sheet(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.get("/api/v1/statements?statement_type=balance_sheet")
    assert response.status_code == 200
    assert response.json()["statement_type"] == "balance_sheet"


def test_statements_income(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.get("/api/v1/statements?statement_type=income_statement")
    assert response.status_code == 200
    assert response.json()["statement_type"] == "income_statement"


def test_statements_trial_balance(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.get("/api/v1/statements?statement_type=trial_balance")
    assert response.status_code == 200
    assert response.json()["statement_type"] == "trial_balance"


def test_statements_unsupported_type(monkeypatch):
    client = _make_client(monkeypatch)
    response = client.get("/api/v1/statements?statement_type=cash_flow")
    assert response.status_code == 400
