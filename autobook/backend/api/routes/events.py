import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from queues import subscribe

logger = logging.getLogger(__name__)
router = APIRouter()

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved")


@router.get("/api/v1/events")
async def events(request: Request, userId: str | None = None):
    redis = request.app.state.redis

    async def event_stream():
        async for event in subscribe(redis, *CHANNELS):
            if await request.is_disconnected():
                break

            event_user = event.get("user_id")
            if userId and event_user and event_user != userId:
                continue

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
