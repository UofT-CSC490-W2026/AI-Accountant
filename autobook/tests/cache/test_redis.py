from __future__ import annotations

import pytest
import fakeredis.aioredis

from cache.redis import cache_get, cache_set


@pytest.fixture
async def r():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_cache_get_miss(r):
    result = await cache_get(r, "missing-key")
    assert result is None


async def test_cache_get_hit(r):
    await cache_set(r, "key1", {"foo": "bar"})
    result = await cache_get(r, "key1")
    assert result == {"foo": "bar"}


async def test_cache_set_no_ttl(r):
    await cache_set(r, "key2", {"a": 1})
    ttl = await r.ttl("key2")
    assert ttl == -1


async def test_cache_set_with_ttl(r):
    await cache_set(r, "key3", {"a": 1}, ttl=10)
    ttl = await r.ttl("key3")
    assert 0 < ttl <= 10
