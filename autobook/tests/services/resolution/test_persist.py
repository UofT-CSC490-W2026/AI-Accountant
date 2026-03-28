from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import services.resolution.service as resolution_svc


def test_persist_pending_missing_txn_id(monkeypatch):
    monkeypatch.setattr(resolution_svc, "set_status_sync", lambda **kw: None)
    with pytest.raises(ValueError, match="transaction_id"):
        resolution_svc._persist_pending_clarification({"parse_id": "p1"})


def test_persist_pending_txn_not_found(monkeypatch):
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None, close=lambda: None)
    monkeypatch.setattr(resolution_svc, "SessionLocal", lambda: db)
    monkeypatch.setattr(resolution_svc.TransactionDAO, "get_by_id", staticmethod(lambda _db, _tid: None))
    with pytest.raises(ValueError, match="not found"):
        resolution_svc._persist_pending_clarification({"parse_id": "p1", "transaction_id": "txn-1"})
