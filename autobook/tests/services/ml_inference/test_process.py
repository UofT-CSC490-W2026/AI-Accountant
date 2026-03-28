from __future__ import annotations

import services.ml_inference.service as ml_svc


def test_execute_enriches(monkeypatch):
    monkeypatch.setattr(ml_svc, "_persist_transaction_state", lambda msg: msg)
    result = ml_svc.execute({
        "parse_id": "p1",
        "input_text": "Bought printer for $500",
        "source": "manual",
        "currency": "CAD",
        "user_id": "user-1",
    })
    assert result["intent_label"] is not None
    assert "confidence" in result
