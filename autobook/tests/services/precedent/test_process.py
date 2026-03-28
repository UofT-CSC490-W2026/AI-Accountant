from __future__ import annotations

import services.precedent.service as precedent_svc


def test_execute_no_match(monkeypatch):
    monkeypatch.setattr(precedent_svc, "_load_candidates", lambda msg: [])
    result = precedent_svc.execute({"parse_id": "p1", "input_text": "test"})
    assert result["precedent_match"]["matched"] is False
    assert result["precedent_match"]["pattern_id"] is None


def test_execute_returns_confidence(monkeypatch):
    monkeypatch.setattr(precedent_svc, "_load_candidates", lambda msg: [])
    result = precedent_svc.execute({"parse_id": "p1"})
    assert "confidence" in result
    assert "precedent" in result["confidence"]
