"""Typed subscribe — used by SSE endpoint only."""

from __future__ import annotations

from typing import AsyncGenerator

import redis.asyncio as aioredis

from queues.pubsub.client import subscribe

CHANNELS = (
    "entry.posted",
    "clarification.created",
    "clarification.resolved",
    "pipeline.result",
    "pipeline.error",
    "pipeline.stage_started",
)

__all__ = ["events"]


async def events(r: aioredis.Redis, keepalive_interval: float = 0) -> AsyncGenerator[dict | None, None]:
    async for event in subscribe(r, *CHANNELS, keepalive_interval=keepalive_interval):
        yield event
