from __future__ import annotations

import asyncio
import json

import pytest
import fakeredis.aioredis

from queues.pubsub.client import publish_async, publish_sync, subscribe


@pytest.fixture
async def r():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_redis_publish(r):
    pubsub = r.pubsub()
    await pubsub.subscribe("test-channel")

    await publish_async(r, "test-channel", {"type": "test", "value": 42})

    msg = None
    async for message in pubsub.listen():
        if message["type"] == "message":
            msg = json.loads(message["data"])
            break

    await pubsub.unsubscribe("test-channel")
    await pubsub.aclose()
    assert msg == {"type": "test", "value": 42}


async def test_redis_publish_sync(monkeypatch):
    published = []

    class FakeSyncRedis:
        def publish(self, channel, data):
            published.append((channel, data))

    monkeypatch.setattr("queues.pubsub.client._sync_client", FakeSyncRedis())

    publish_sync("ch1", {"type": "event"})
    assert len(published) == 1
    assert published[0][0] == "ch1"


async def test_redis_subscribe(r):
    received = []

    async def reader():
        async for msg in subscribe(r, "sub-channel"):
            received.append(msg)
            break

    task = asyncio.create_task(reader())
    await asyncio.sleep(0.05)
    await publish_async(r, "sub-channel", {"type": "hello"})
    await asyncio.wait_for(task, timeout=2)

    assert len(received) == 1
    assert received[0]["type"] == "hello"
