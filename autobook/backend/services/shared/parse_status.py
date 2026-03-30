from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis as sync_redis
import redis.asyncio as aioredis

from config import get_settings

STATUS_TTL_SECONDS = 60 * 60 * 24
TERMINAL_STATUSES = {"auto_posted", "needs_clarification", "resolved", "rejected", "failed"}

_sync_client: sync_redis.Redis | None = None


def _key(parse_id: str) -> str:
    return f"parse_status:{parse_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_confidence(confidence: dict | None) -> dict | None:
    if confidence is None:
        return None
    payload = dict(confidence)
    payload.setdefault("auto_post_threshold", get_settings().AUTO_POST_THRESHOLD)
    return payload


def _normalize_batch(batch: dict | None) -> dict | None:
    if batch is None:
        return None

    payload = dict(batch)
    items = list(payload.get("items") or [])
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_items.append(
            {
                "child_parse_id": item.get("child_parse_id"),
                "statement_index": item.get("statement_index"),
                "input_text": item.get("input_text"),
                "status": item.get("status"),
                "clarification_id": item.get("clarification_id"),
                "journal_entry_id": item.get("journal_entry_id"),
                "error": item.get("error"),
            }
        )
    normalized_items.sort(key=lambda item: int(item.get("statement_index") or 0))
    payload["items"] = normalized_items
    return payload


def _get_sync_redis() -> sync_redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = sync_redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _sync_client


def _normalize_proposed_entry(payload: dict | None) -> dict | None:
    if payload is None:
        return None

    if "entry" in payload and "lines" in payload:
        entry = dict(payload.get("entry") or {})
        return {
            "journal_entry_id": entry.get("journal_entry_id") or entry.get("id"),
            "lines": list(payload.get("lines") or []),
        }

    return {
        "journal_entry_id": payload.get("journal_entry_id") or payload.get("id"),
        "lines": list(payload.get("lines") or []),
    }


def _merge_status(current: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current or {})
    for key, value in updates.items():
        if value is None:
            continue
        if key == "proposed_entry":
            merged[key] = _normalize_proposed_entry(value)
            continue
        if key == "confidence":
            merged[key] = _normalize_confidence(value)
            continue
        if key == "batch":
            merged[key] = _normalize_batch(value)
            continue
        merged[key] = value

    merged.setdefault("occurred_at", _now_iso())
    merged["updated_at"] = _now_iso()
    return merged


def _load_sync(parse_id: str) -> dict[str, Any] | None:
    try:
        raw = _get_sync_redis().get(_key(parse_id))
    except Exception:
        return None
    if raw is None:
        return None
    return json.loads(raw)


async def load_status(redis: aioredis.Redis, parse_id: str) -> dict[str, Any] | None:
    if not hasattr(redis, "get"):
        return None
    raw = await redis.get(_key(parse_id))
    if raw is None:
        return None
    return json.loads(raw)


def set_status_sync(
    *,
    parse_id: str,
    user_id: str,
    status: str,
    stage: str | None = None,
    input_text: str | None = None,
    explanation: str | None = None,
    confidence: dict | None = None,
    proposed_entry: dict | None = None,
    clarification_id: str | None = None,
    journal_entry_id: str | None = None,
    error: str | None = None,
    batch: dict | None = None,
) -> dict[str, Any]:
    current = _load_sync(parse_id)
    payload = _merge_status(
        current,
        {
            "parse_id": parse_id,
            "user_id": user_id,
            "status": status,
            "stage": stage,
            "input_text": input_text,
            "explanation": explanation,
            "confidence": confidence,
            "proposed_entry": proposed_entry,
            "clarification_id": clarification_id,
            "journal_entry_id": journal_entry_id,
            "error": error,
            "batch": batch,
        },
    )
    try:
        _get_sync_redis().setex(_key(parse_id), STATUS_TTL_SECONDS, json.dumps(payload))
    except Exception:
        return payload
    return payload


async def set_status(
    redis: aioredis.Redis,
    *,
    parse_id: str,
    user_id: str,
    status: str,
    stage: str | None = None,
    input_text: str | None = None,
    explanation: str | None = None,
    confidence: dict | None = None,
    proposed_entry: dict | None = None,
    clarification_id: str | None = None,
    journal_entry_id: str | None = None,
    error: str | None = None,
    batch: dict | None = None,
) -> dict[str, Any]:
    current = await load_status(redis, parse_id)
    payload = _merge_status(
        current,
        {
            "parse_id": parse_id,
            "user_id": user_id,
            "status": status,
            "stage": stage,
            "input_text": input_text,
            "explanation": explanation,
            "confidence": confidence,
            "proposed_entry": proposed_entry,
            "clarification_id": clarification_id,
            "journal_entry_id": journal_entry_id,
            "error": error,
            "batch": batch,
        },
    )
    if hasattr(redis, "set"):
        await redis.set(_key(parse_id), json.dumps(payload), ex=STATUS_TTL_SECONDS)
    return payload


def summarize_batch_results(
    *,
    total_statements: int,
    items: list[dict],
) -> tuple[str, dict[str, int]]:
    counts = {
        "auto_posted": 0,
        "needs_clarification": 0,
        "resolved": 0,
        "rejected": 0,
        "failed": 0,
    }
    for item in items:
        status = str(item.get("status") or "").lower()
        if status in counts:
            counts[status] += 1

    completed_statements = sum(counts.values())
    if completed_statements < total_statements:
        return "processing", counts
    if counts["needs_clarification"] > 0:
        return "needs_clarification", counts
    if counts["failed"] > 0:
        return "failed", counts
    if counts["auto_posted"] == total_statements:
        return "auto_posted", counts
    if counts["rejected"] == total_statements:
        return "rejected", counts
    return "resolved", counts


def build_batch_summary(
    *,
    total_statements: int,
    items: list[dict],
) -> dict[str, Any]:
    status, counts = summarize_batch_results(total_statements=total_statements, items=items)
    completed_statements = sum(counts.values())
    return {
        "total_statements": total_statements,
        "completed_statements": completed_statements,
        "pending_statements": max(total_statements - completed_statements, 0),
        "auto_posted_count": counts["auto_posted"],
        "needs_clarification_count": counts["needs_clarification"],
        "resolved_count": counts["resolved"],
        "rejected_count": counts["rejected"],
        "failed_count": counts["failed"],
        "items": items,
        "status": status,
    }


def record_batch_result_sync(
    *,
    parent_parse_id: str,
    child_parse_id: str,
    user_id: str,
    statement_index: int,
    total_statements: int,
    status: str,
    input_text: str | None = None,
    clarification_id: str | None = None,
    journal_entry_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    current = _load_sync(parent_parse_id) or {}
    current_batch = dict(current.get("batch") or {})
    items_by_child: dict[str, dict[str, Any]] = {
        str(item.get("child_parse_id")): dict(item)
        for item in current_batch.get("items") or []
        if item.get("child_parse_id")
    }
    items_by_child[child_parse_id] = {
        "child_parse_id": child_parse_id,
        "statement_index": statement_index,
        "input_text": input_text,
        "status": status,
        "clarification_id": clarification_id,
        "journal_entry_id": journal_entry_id,
        "error": error,
    }
    items = sorted(items_by_child.values(), key=lambda item: int(item.get("statement_index") or 0))
    batch = build_batch_summary(total_statements=total_statements, items=items)
    explanation = _batch_explanation(batch)
    payload = _merge_status(
        current,
        {
            "parse_id": parent_parse_id,
            "user_id": user_id,
            "status": batch["status"],
            "stage": current.get("stage") or "batch",
            "explanation": explanation,
            "batch": batch,
            "clarification_id": clarification_id if batch["status"] == "needs_clarification" else None,
            "journal_entry_id": journal_entry_id if batch["total_statements"] == 1 else None,
            "error": error if batch["status"] == "failed" else None,
        },
    )
    try:
        _get_sync_redis().setex(_key(parent_parse_id), STATUS_TTL_SECONDS, json.dumps(payload))
    except Exception:
        return payload
    return payload


def _batch_explanation(batch: dict[str, Any]) -> str:
    total = int(batch.get("total_statements") or 0)
    return (
        f"Processed {total} statements: "
        f"{batch.get('auto_posted_count', 0)} auto-posted, "
        f"{batch.get('needs_clarification_count', 0)} awaiting clarification, "
        f"{batch.get('resolved_count', 0)} resolved, "
        f"{batch.get('rejected_count', 0)} rejected, "
        f"{batch.get('failed_count', 0)} failed."
    )
