from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import services.ml_inference.service as ml_svc


def test_execute_high_confidence_asset(monkeypatch):
    monkeypatch.setattr(ml_svc, "_persist_transaction_state", lambda msg: msg)
    result = ml_svc.execute({
        "parse_id": "p1",
        "input_text": "Bought printer for $500",
        "source": "manual",
        "currency": "CAD",
        "user_id": "u1",
    })
    ml_conf = (result.get("confidence") or {}).get("ml", 0)
    if ml_conf >= 0.95:
        assert "proposed_entry" in result
        assert result["confidence"]["overall"] == ml_conf


def test_persist_transaction_state_store_false():
    msg = {"parse_id": "p1", "store": False}
    result = ml_svc._persist_transaction_state(msg)
    assert result is msg


def test_execute_high_confidence_adds_proposed_entry(monkeypatch):
    monkeypatch.setattr(ml_svc, "_persist_transaction_state", lambda msg: msg)

    class HighConfService:
        def enrich(self, message):
            return {**message, "confidence": {"ml": 0.97}, "intent_label": "asset_purchase", "entities": {"amount": 500}}

    monkeypatch.setattr(ml_svc, "get_inference_service", lambda: HighConfService())
    result = ml_svc.execute({
        "parse_id": "p1",
        "input_text": "Bought printer for $500",
        "source": "manual",
        "currency": "CAD",
        "user_id": "u1",
        "amount": 500,
    })
    assert "proposed_entry" in result
    assert result["confidence"]["overall"] == 0.97


def test_persist_transaction_state_store_true(monkeypatch):
    txn = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(ml_svc, "SessionLocal", lambda: SimpleNamespace(commit=lambda: None, rollback=lambda: None, close=lambda: None))
    monkeypatch.setattr(
        "services.shared.transaction_persistence.ensure_transaction_for_message",
        lambda _db, _msg: (None, txn),
    )
    result = ml_svc._persist_transaction_state({"parse_id": "p1", "store": True})
    assert result["transaction_id"] == str(txn.id)
