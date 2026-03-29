from __future__ import annotations

import json

import pytest
import fakeredis
import fakeredis.aioredis

import services.shared.parse_status as ps
from config import get_settings


@pytest.fixture(autouse=True)
def patch_sync_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(ps, "_sync_client", fake)
    yield fake


@pytest.fixture
async def async_redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


def test_merge_status_fresh():
    result = ps._merge_status(None, {"parse_id": "p1", "status": "accepted"})
    assert result["parse_id"] == "p1"
    assert result["status"] == "accepted"
    assert "occurred_at" in result
    assert "updated_at" in result


def test_merge_status_skips_none():
    result = ps._merge_status({"parse_id": "p1"}, {"status": "ok", "error": None})
    assert "error" not in result


def test_merge_status_proposed_entry():
    result = ps._merge_status(None, {
        "proposed_entry": {"entry": {"journal_entry_id": "j1"}, "lines": [{"a": 1}]},
    })
    assert result["proposed_entry"]["journal_entry_id"] == "j1"
    assert result["proposed_entry"]["lines"] == [{"a": 1}]


def test_merge_status_confidence_adds_threshold():
    result = ps._merge_status(None, {
        "confidence": {"overall": 0.97, "ml": 0.97},
    })
    assert result["confidence"]["overall"] == 0.97
    assert result["confidence"]["auto_post_threshold"] == get_settings().AUTO_POST_THRESHOLD


def test_normalize_proposed_entry_none():
    assert ps._normalize_proposed_entry(None) is None


def test_normalize_proposed_entry_flat():
    result = ps._normalize_proposed_entry({"journal_entry_id": "j1", "lines": []})
    assert result["journal_entry_id"] == "j1"


def test_normalize_confidence_none():
    assert ps._normalize_confidence(None) is None


def test_normalize_confidence_adds_threshold():
    result = ps._normalize_confidence({"overall": 0.5})
    assert result["auto_post_threshold"] == get_settings().AUTO_POST_THRESHOLD


def test_build_batch_summary_counts_items():
    result = ps.build_batch_summary(
        total_statements=3,
        items=[
            {"child_parse_id": "p1_s1", "statement_index": 0, "status": "auto_posted"},
            {"child_parse_id": "p1_s2", "statement_index": 1, "status": "needs_clarification"},
        ],
    )

    assert result["completed_statements"] == 2
    assert result["pending_statements"] == 1
    assert result["auto_posted_count"] == 1
    assert result["needs_clarification_count"] == 1
    assert result["status"] == "processing"


def test_record_batch_result_sync_tracks_child_results():
    ps.set_status_sync(
        parse_id="parent-1",
        user_id="u1",
        status="accepted",
        batch=ps.build_batch_summary(total_statements=2, items=[]),
    )

    ps.record_batch_result_sync(
        parent_parse_id="parent-1",
        child_parse_id="parent-1_s1",
        user_id="u1",
        statement_index=0,
        total_statements=2,
        status="auto_posted",
        input_text="Bought laptop",
        journal_entry_id="je-1",
    )
    result = ps.record_batch_result_sync(
        parent_parse_id="parent-1",
        child_parse_id="parent-1_s2",
        user_id="u1",
        statement_index=1,
        total_statements=2,
        status="needs_clarification",
        input_text="Transferred money",
        clarification_id="cl-1",
    )

    assert result["status"] == "needs_clarification"
    assert result["batch"]["completed_statements"] == 2
    assert result["batch"]["needs_clarification_count"] == 1
    assert result["batch"]["items"][1]["clarification_id"] == "cl-1"


def test_set_status_sync():
    result = ps.set_status_sync(parse_id="p1", user_id="u1", status="processing", stage="normalizer")
    assert result["parse_id"] == "p1"
    assert result["status"] == "processing"


def test_set_status_sync_updates():
    ps.set_status_sync(parse_id="p1", user_id="u1", status="accepted")
    result = ps.set_status_sync(parse_id="p1", user_id="u1", status="processing", stage="normalizer")
    assert result["status"] == "processing"
    assert result["stage"] == "normalizer"


def test_load_sync_miss():
    result = ps._load_sync("nonexistent")
    assert result is None


def test_load_sync_hit(patch_sync_redis):
    patch_sync_redis.set("parse_status:p1", json.dumps({"parse_id": "p1"}))
    result = ps._load_sync("p1")
    assert result["parse_id"] == "p1"


@pytest.mark.asyncio
async def test_load_status_async(async_redis):
    await async_redis.set("parse_status:p1", json.dumps({"parse_id": "p1"}))
    result = await ps.load_status(async_redis, "p1")
    assert result["parse_id"] == "p1"


@pytest.mark.asyncio
async def test_load_status_async_miss(async_redis):
    result = await ps.load_status(async_redis, "missing")
    assert result is None


@pytest.mark.asyncio
async def test_set_status_async(async_redis):
    result = await ps.set_status(async_redis, parse_id="p1", user_id="u1", status="accepted")
    assert result["parse_id"] == "p1"
    assert result["status"] == "accepted"
    stored = await async_redis.get("parse_status:p1")
    assert json.loads(stored)["status"] == "accepted"


@pytest.mark.asyncio
async def test_load_status_no_redis():
    result = await ps.load_status(object(), "p1")
    assert result is None


@pytest.mark.asyncio
async def test_set_status_no_redis():
    result = await ps.set_status(object(), parse_id="p1", user_id="u1", status="ok")
    assert result["parse_id"] == "p1"
