from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import services.resolution.service as resolution_svc


def _setup_resolution(monkeypatch):
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None, close=lambda: None)
    user = SimpleNamespace(id=uuid4())
    transaction = SimpleNamespace(id=uuid4(), user_id=user.id)
    task = SimpleNamespace(id=uuid4())
    enqueued, published, created = [], [], []

    monkeypatch.setattr(resolution_svc, "SessionLocal", lambda: db)
    monkeypatch.setattr(resolution_svc, "set_status_sync", lambda **kw: None)
    monkeypatch.setattr(resolution_svc.TransactionDAO, "get_by_id", staticmethod(lambda _db, _tid: transaction))
    monkeypatch.setattr(resolution_svc.ClarificationDAO, "insert", staticmethod(
        lambda **kwargs: task
    ))
    monkeypatch.setattr(resolution_svc.pub, "clarification_resolved", lambda **kw: published.append(kw))
    monkeypatch.setattr(resolution_svc.pub, "clarification_created", lambda **kw: created.append(kw))
    monkeypatch.setattr(resolution_svc.sqs.enqueue, "posting", lambda msg: enqueued.append(msg))

    return {"enqueued": enqueued, "published": published, "created": created, "task": task}


def test_process_creates_task(monkeypatch):
    ctx = _setup_resolution(monkeypatch)
    resolution_svc.execute({"parse_id": "p1", "input_text": "unclear", "user_id": "u1", "transaction_id": "txn1"})
    assert len(ctx["enqueued"]) == 0
    assert len(ctx["published"]) == 0
    assert len(ctx["created"]) == 1


def test_process_routes_resolved(monkeypatch):
    ctx = _setup_resolution(monkeypatch)
    resolution_svc.execute({"parse_id": "p1", "input_text": "approved", "user_id": "u1", "clarification": {"status": "approved"}})
    assert len(ctx["enqueued"]) == 1


def test_process_event_created(monkeypatch):
    ctx = _setup_resolution(monkeypatch)
    resolution_svc.execute({"parse_id": "p1", "input_text": "unclear", "user_id": "u1", "transaction_id": "txn1"})
    assert ctx["created"][0]["parse_id"] == "p1"


def test_process_event_resolved(monkeypatch):
    ctx = _setup_resolution(monkeypatch)
    resolution_svc.execute({"parse_id": "p1", "input_text": "approved", "user_id": "u1", "clarification": {"status": "resolved"}})
    assert ctx["published"][0]["status"] == "resolved"


def test_process_skips_rejected(monkeypatch):
    ctx = _setup_resolution(monkeypatch)
    resolution_svc.execute({"parse_id": "p1", "input_text": "rejected", "user_id": "u1", "clarification": {"status": "rejected"}})
    assert len(ctx["enqueued"]) == 0
    assert ctx["published"][0]["status"] == "rejected"
