from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from services.normalizer import process as normalizer_process


class FakeDB:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_normalizer_persists_canonical_transaction_before_enqueue(monkeypatch) -> None:
    db = FakeDB()
    user = SimpleNamespace(id=uuid4())
    transaction = SimpleNamespace(id=uuid4())
    inserted: dict = {}
    enqueued: list[tuple[str, dict]] = []

    monkeypatch.setattr(normalizer_process, "SessionLocal", lambda: db)
    monkeypatch.setattr(normalizer_process, "resolve_local_user", lambda _db, _external_user_id: user)

    def fake_insert(**kwargs):
        inserted.update(kwargs)
        return transaction

    monkeypatch.setattr(normalizer_process.TransactionDAO, "insert", staticmethod(fake_insert))
    monkeypatch.setattr(
        normalizer_process,
        "enqueue",
        lambda queue_url, payload: enqueued.append((queue_url, payload)),
    )

    normalizer_process.process(
        {
            "parse_id": "parse_normalizer_1",
            "input_text": "Bought a laptop from Apple for $2400",
            "user_id": "demo-user-1",
            "source": "manual",
            "currency": "CAD",
        }
    )

    assert inserted["user_id"] == user.id
    assert inserted["normalized_description"] == "bought a laptop from apple for $2400"
    assert inserted["amount"] is None
    assert inserted["counterparty"] is None
    assert inserted["amount_mentions"] == [{"text": "$2400", "value": 2400.0}]
    assert inserted["party_mentions"] == [{"text": "Apple", "value": "Apple"}]
    assert db.committed is True
    assert enqueued[0][1]["transaction_id"] == str(transaction.id)
    assert enqueued[0][1]["normalized_description"] == inserted["normalized_description"]
    assert enqueued[0][1]["amount_mentions"] == inserted["amount_mentions"]
