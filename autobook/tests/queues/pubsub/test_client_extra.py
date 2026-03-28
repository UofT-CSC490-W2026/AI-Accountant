from __future__ import annotations

import asyncio
import json

import pytest
import fakeredis.aioredis

from queues.pubsub.client import get_redis, subscribe


async def test_get_redis():
    r = await get_redis("redis://localhost:6379/0")
    assert r is not None
    await r.aclose()


async def test_subscribe_keepalive():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    received = []

    async def reader():
        async for msg in subscribe(r, "ch", keepalive_interval=0.05):
            received.append(msg)
            if msg is None:
                break

    task = asyncio.create_task(reader())
    await asyncio.wait_for(task, timeout=2)
    await r.aclose()

    assert None in received
