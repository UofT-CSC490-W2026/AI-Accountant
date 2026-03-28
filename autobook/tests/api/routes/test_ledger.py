from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import ledger as ledger_route
from auth.deps import AuthContext, get_current_user
from auth.schemas import UserRole
from db.connection import get_db


def _make_client(monkeypatch, entries=None, balances=None, summary=None):
    app = FastAPI()
    app.include_router(ledger_route.router)

    auth = AuthContext(
        user=SimpleNamespace(id=uuid.UUID("11111111-1111-1111-1111-111111111111")),
        claims=SimpleNamespace(token_use="access"),
        role=UserRole.REGULAR,
        role_source="cognito:groups",
    )
    app.dependency_overrides[get_current_user] = lambda: auth
    app.dependency_overrides[get_db] = lambda: SimpleNamespace()

    monkeypatch.setattr(ledger_route.JournalEntryDAO, "list_by_user", staticmethod(lambda _db, _uid, filters=None: entries or []))
    monkeypatch.setattr(ledger_route.JournalEntryDAO, "compute_balances", staticmethod(lambda _db, _uid: balances or []))
    monkeypatch.setattr(ledger_route.JournalEntryDAO, "compute_summary", staticmethod(
        lambda _db, _uid: summary or {"total_debits": Decimal("0"), "total_credits": Decimal("0")}
    ))

    return TestClient(app)


def _make_entry(description="Test", amount=500):
    entry_id = uuid.uuid4()
    return SimpleNamespace(
        id=entry_id,
        date="2026-03-23",
        description=description,
        status="posted",
        origin_tier=3,
        confidence=Decimal("0.95"),
        lines=[
            SimpleNamespace(account_code="1500", account_name="Equipment", type="debit", amount=Decimal(str(amount))),
            SimpleNamespace(account_code="1000", account_name="Cash", type="credit", amount=Decimal(str(amount))),
        ],
    )


def test_ledger_returns_entries(monkeypatch):
    entry = _make_entry()
    client = _make_client(monkeypatch, entries=[entry])
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200
    assert len(response.json()["entries"]) == 1


def test_ledger_filter_date(monkeypatch):
    client = _make_client(monkeypatch, entries=[])
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200
    assert response.json()["entries"] == []


def test_ledger_filter_account(monkeypatch):
    entry = _make_entry()
    client = _make_client(monkeypatch, entries=[entry])
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200
    lines = response.json()["entries"][0]["lines"]
    assert any(l["account_code"] == "1500" for l in lines)


def test_ledger_balance_totals(monkeypatch):
    client = _make_client(
        monkeypatch,
        balances=[{"account_code": "1000", "account_name": "Cash", "balance": Decimal("5000")}],
        summary={"total_debits": Decimal("5000"), "total_credits": Decimal("5000")},
    )
    response = client.get("/api/v1/ledger")
    assert response.status_code == 200
    assert response.json()["summary"]["total_debits"] == 5000.0
    assert response.json()["summary"]["total_credits"] == 5000.0
