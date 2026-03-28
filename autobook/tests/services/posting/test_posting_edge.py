from __future__ import annotations

from services.posting.service import _json_safe, _serialize_proposed_entry
from datetime import datetime, timezone
from uuid import uuid4


def test_json_safe_datetime():
    dt = datetime(2026, 3, 23, tzinfo=timezone.utc)
    assert _json_safe(dt) == dt.isoformat()


def test_json_safe_uuid():
    u = uuid4()
    assert _json_safe(u) == str(u)


def test_json_safe_string():
    assert _json_safe("hello") == "hello"


def test_serialize_proposed_entry_none():
    assert _serialize_proposed_entry(None) is None


def test_serialize_proposed_entry_with_id():
    result = _serialize_proposed_entry(
        {"entry": {"date": "2026-01-01"}, "lines": [{"a": 1}]},
        journal_entry_id="j1",
    )
    assert result["entry"]["journal_entry_id"] == "j1"
