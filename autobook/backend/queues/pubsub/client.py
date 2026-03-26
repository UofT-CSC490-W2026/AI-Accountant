from __future__ import annotations

import json
from typing import AsyncGenerator

import redis as sync_redis
import redis.asyncio as aioredis


async def get_redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)


# --- Sync client (Lambda workers) ---

_sync_client: sync_redis.Redis | None = None


def _get_sync_redis() -> sync_redis.Redis:
    global _sync_client
    if _sync_client is None:
        from config import get_settings
        _sync_client = sync_redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _sync_client


def publish_sync(channel: str, payload: dict) -> None:
    r = _get_sync_redis()
    r.publish(channel, json.dumps(payload))


# --- Async (API service) ---

async def publish_async(r: aioredis.Redis, channel: str, payload: dict) -> None:
    await r.publish(channel, json.dumps(payload))


async def subscribe(r: aioredis.Redis, *channels: str, keepalive_interval: float = 0) -> AsyncGenerator[dict | None, None]:
    pubsub = r.pubsub()
    await pubsub.subscribe(*channels)
    try:
        if keepalive_interval > 0:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=keepalive_interval)
                if message is None:
                    yield None  # keepalive tick
                elif message["type"] == "message":
                    yield json.loads(message["data"])
        else:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
