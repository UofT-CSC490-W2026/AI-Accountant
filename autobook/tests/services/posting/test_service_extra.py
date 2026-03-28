from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import services.posting.service as posting_svc


def test_compute_parse_time_ms_none():
    assert posting_svc._compute_parse_time_ms({}) is None


def test_compute_parse_time_ms_invalid():
    assert posting_svc._compute_parse_time_ms({"submitted_at": "not-a-date"}) is None


def test_normalize_proposed_entry_passthrough():
    pe = {"entry": {"date": "2026-01-01"}, "lines": []}
    assert posting_svc._normalize_proposed_entry({"proposed_entry": pe}) == pe


def test_normalize_proposed_entry_wraps():
    pe = {"lines": [{"account_code": "1000", "type": "debit", "amount": 100}]}
    result = posting_svc._normalize_proposed_entry({"proposed_entry": pe, "input_text": "test"})
    assert result["entry"]["origin_tier"] == 3
    assert result["entry"]["description"] == "test"


def test_execute_missing_transaction_id(monkeypatch):
    monkeypatch.setattr(posting_svc, "set_status_sync", lambda **kw: None)
    with pytest.raises(ValueError, match="transaction_id"):
        posting_svc.execute({"parse_id": "p1", "user_id": "u1"})
