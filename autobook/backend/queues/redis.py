import json
from typing import AsyncGenerator

import redis.asyncio as aioredis


async def get_redis(url: str) -> aioredis.Redis:
    return aioredis.from_url(url, decode_responses=True)


async def enqueue(r: aioredis.Redis, queue_name: str, payload: dict) -> None:
    await r.lpush(queue_name, json.dumps(payload))


async def dequeue(r: aioredis.Redis, queue_name: str, timeout: int = 0) -> dict | None:
    result = await r.brpop(queue_name, timeout=timeout)
    if result is None:
        return None
    _, message = result
    return json.loads(message)


async def publish(r: aioredis.Redis, channel: str, payload: dict) -> None:
    await r.publish(channel, json.dumps(payload))


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
