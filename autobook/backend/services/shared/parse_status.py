from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis as sync_redis
import redis.asyncio as aioredis

from config import get_settings

STATUS_TTL_SECONDS = 60 * 60 * 24

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
        },
    )
    if hasattr(redis, "set"):
        await redis.set(_key(parse_id), json.dumps(payload), ex=STATUS_TTL_SECONDS)
    return payload
