import json
from typing import AsyncGenerator

import redis as sync_redis
import redis.asyncio as aioredis


async def get_redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)


async def publish(r: aioredis.Redis, channel: str, payload: dict) -> None:
    await r.publish(channel, json.dumps(payload))


# --- Sync publish for workers (Lambda handler / dequeue loop) ---

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


async def subscribe(r: aioredis.Redis, *channels: str) -> AsyncGenerator[dict, None]:
    pubsub = r.pubsub()
    await pubsub.subscribe(*channels)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
