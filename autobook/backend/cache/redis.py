import json

import redis.asyncio as aioredis


async def cache_get(r: aioredis.Redis, key: str) -> dict | None:
    value = await r.get(key)
    if value is None:
        return None
    return json.loads(value)


async def cache_set(r: aioredis.Redis, key: str, value: dict, ttl: int | None = None) -> None:
    serialized = json.dumps(value)
    if ttl is not None:
        await r.set(key, serialized, ex=ttl)
    else:
        await r.set(key, serialized)
