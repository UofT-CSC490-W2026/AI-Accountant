"""Targeted gap tests for parse_status.py — covers specific missed lines.

Lines targeted:
  36        _normalize_batch returns None when batch is None
  43        _normalize_batch skips non-dict items
  63        _get_sync_redis lazy-initialises the client
  108-109   _load_sync catches Redis exception and returns None
  159-160   set_status_sync catches Redis setex exception, still returns payload
  225-231   summarize_batch_results: failed, all-auto_posted, all-rejected, resolved
  303-304   record_batch_result_sync catches Redis setex exception
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
import fakeredis

import services.shared.parse_status as ps


@pytest.fixture(autouse=True)
def patch_sync_redis(monkeypatch):
    """Provide a fakeredis client for every test unless overridden."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(ps, "_sync_client", fake)
    yield fake


# ── Line 36: _normalize_batch(None) returns None ─────────────────────────

def test_normalize_batch_returns_none_for_none():
    assert ps._normalize_batch(None) is None


# ── Line 43: _normalize_batch skips non-dict items ───────────────────────

def test_normalize_batch_skips_non_dict_items():
    batch = {"items": ["not-a-dict", 42, None, {"child_parse_id": "c1", "statement_index": 0}]}
    result = ps._normalize_batch(batch)
    assert len(result["items"]) == 1
    assert result["items"][0]["child_parse_id"] == "c1"


# ── Line 63: _get_sync_redis lazy-initialises ────────────────────────────

def test_get_sync_redis_lazy_init(monkeypatch):
    """When _sync_client is None, _get_sync_redis creates a new client."""
    monkeypatch.setattr(ps, "_sync_client", None)
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("redis.from_url", lambda *a, **kw: fake)
    client = ps._get_sync_redis()
    assert client is fake


# ── Lines 108-109: _load_sync returns None on Redis exception ────────────

def test_load_sync_returns_none_on_redis_exception(monkeypatch):
    broken = MagicMock()
    broken.get.side_effect = ConnectionError("redis down")
    monkeypatch.setattr(ps, "_sync_client", broken)
    assert ps._load_sync("some-id") is None


# ── Lines 159-160: set_status_sync catches setex exception ───────────────

def test_set_status_sync_returns_payload_on_setex_exception(monkeypatch):
    broken = MagicMock()
    broken.get.return_value = None  # _load_sync returns None (no current)
    broken.setex.side_effect = ConnectionError("redis down")
    monkeypatch.setattr(ps, "_sync_client", broken)
    result = ps.set_status_sync(parse_id="p1", user_id="u1", status="processing")
    assert result["parse_id"] == "p1"
    assert result["status"] == "processing"


# ── Lines 225-231: summarize_batch_results branches ──────────────────────

def test_summarize_batch_results_failed_takes_priority():
    """When all complete and at least one failed, overall status is 'failed'."""
    status, counts = ps.summarize_batch_results(
        total_statements=2,
        items=[
            {"status": "auto_posted"},
            {"status": "failed"},
        ],
    )
    assert status == "failed"
    assert counts["failed"] == 1


def test_summarize_batch_results_all_auto_posted():
    """When every statement is auto_posted, overall status is 'auto_posted'."""
    status, counts = ps.summarize_batch_results(
        total_statements=2,
        items=[
            {"status": "auto_posted"},
            {"status": "auto_posted"},
        ],
    )
    assert status == "auto_posted"
    assert counts["auto_posted"] == 2


def test_summarize_batch_results_all_rejected():
    """When every statement is rejected, overall status is 'rejected'."""
    status, counts = ps.summarize_batch_results(
        total_statements=2,
        items=[
            {"status": "rejected"},
            {"status": "rejected"},
        ],
    )
    assert status == "rejected"
    assert counts["rejected"] == 2


def test_summarize_batch_results_mixed_resolved():
    """When all complete but mix of resolved/auto_posted, fallback is 'resolved'."""
    status, counts = ps.summarize_batch_results(
        total_statements=2,
        items=[
            {"status": "auto_posted"},
            {"status": "resolved"},
        ],
    )
    assert status == "resolved"


# ── Lines 303-304: record_batch_result_sync catches setex exception ──────

def test_record_batch_result_sync_returns_payload_on_redis_exception(monkeypatch):
    """Even when Redis setex fails, the merged payload is still returned."""
    broken = MagicMock()
    broken.get.return_value = None
    broken.setex.side_effect = ConnectionError("redis down")
    monkeypatch.setattr(ps, "_sync_client", broken)
    result = ps.record_batch_result_sync(
        parent_parse_id="parent-1",
        child_parse_id="parent-1_s1",
        user_id="u1",
        statement_index=0,
        total_statements=1,
        status="auto_posted",
    )
    assert result["parse_id"] == "parent-1"
    assert result["batch"]["auto_posted_count"] == 1
