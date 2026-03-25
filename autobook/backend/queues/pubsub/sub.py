"""Typed subscribe — used by SSE endpoint only."""

from __future__ import annotations

from typing import AsyncGenerator

import redis.asyncio as aioredis

from queues.pubsub.client import subscribe

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved", "pipeline.result", "pipeline.error")

__all__ = ["events"]


async def events(r: aioredis.Redis) -> AsyncGenerator[dict, None]:
    async for event in subscribe(r, *CHANNELS):
        yield event
