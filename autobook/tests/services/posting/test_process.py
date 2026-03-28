from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import services.posting.service as posting_svc


def _setup(monkeypatch):
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None, close=lambda: None)
    user = SimpleNamespace(id=uuid4())
    transaction = SimpleNamespace(id=uuid4(), user_id=user.id)
    journal_entry = SimpleNamespace(id=uuid4())
    enqueued, published, inserted = [], [], {}

    monkeypatch.setattr(posting_svc, "SessionLocal", lambda: db)
    monkeypatch.setattr(posting_svc, "set_status_sync", lambda **kw: None)
    monkeypatch.setattr(posting_svc.TransactionDAO, "get_by_id", staticmethod(lambda _db, _tid: transaction))

    def fake_insert(_db, user_id, entry_payload, line_payload):
        inserted["user_id"] = user_id
        inserted["entry"] = entry_payload
        inserted["lines"] = line_payload
        return journal_entry

    monkeypatch.setattr(posting_svc.JournalEntryDAO, "insert_with_lines", staticmethod(fake_insert))
    monkeypatch.setattr(posting_svc.pub, "entry_posted", lambda **kw: published.append(kw))
    monkeypatch.setattr(posting_svc.sqs.enqueue, "flywheel", lambda msg: enqueued.append(msg))

    return {"user": user, "transaction": transaction, "journal_entry": journal_entry,
            "enqueued": enqueued, "published": published, "inserted": inserted}


MSG = {
    "parse_id": "p1", "input_text": "Bought printer for $500", "user_id": "user-1",
    "transaction_id": "some-txn-id",
    "proposed_entry": {
        "entry": {"date": "2026-03-23", "description": "Bought printer"},
        "lines": [
            {"account_code": "1500", "type": "debit", "amount": 500},
            {"account_code": "1000", "type": "credit", "amount": 500},
        ],
    },
}


def test_process_inserts_entry(monkeypatch):
    ctx = _setup(monkeypatch)
    posting_svc.execute(MSG)
    assert ctx["inserted"]["user_id"] == ctx["transaction"].user_id
    assert len(ctx["inserted"]["lines"]) == 2


def test_process_publishes_event(monkeypatch):
    ctx = _setup(monkeypatch)
    posting_svc.execute(MSG)
    assert ctx["published"][0]["journal_entry_id"] == str(ctx["journal_entry"].id)


def test_process_forwards_flywheel(monkeypatch):
    ctx = _setup(monkeypatch)
    posting_svc.execute(MSG)
    assert len(ctx["enqueued"]) == 1
    assert ctx["enqueued"][0]["journal_entry_id"] == str(ctx["journal_entry"].id)


def test_process_with_parse_time(monkeypatch):
    from datetime import datetime, timezone
    ctx = _setup(monkeypatch)
    message = {**MSG, "submitted_at": datetime.now(timezone.utc).isoformat()}
    posting_svc.execute(message)
    assert ctx["published"][0]["parse_time_ms"] is not None


def test_process_no_proposed_entry(monkeypatch):
    ctx = _setup(monkeypatch)
    with pytest.raises(ValueError, match="proposed entry"):
        posting_svc.execute({**MSG, "proposed_entry": None})


def test_process_normalizes_entry(monkeypatch):
    ctx = _setup(monkeypatch)
    message = {**MSG, "proposed_entry": {"lines": [{"account_code": "1500", "type": "debit", "amount": 500}]}}
    posting_svc.execute(message)
    assert ctx["inserted"]["entry"]["description"] == "Bought printer for $500"
    assert ctx["inserted"]["entry"]["origin_tier"] == 3
