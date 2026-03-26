import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.deps import resolve_auth_context_from_request
from db.connection import SessionLocal
from queues.pubsub import sub

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/v1/events")
async def events(request: Request):
    redis = request.app.state.redis
    db: Session = SessionLocal()
    try:
        current_user = resolve_auth_context_from_request(request, db)
    finally:
        db.close()

    async def event_stream():
        # Send initial keepalive so the client knows the connection is live
        yield ": keepalive\n\n"

        async for event in sub.events(redis, keepalive_interval=30):
            if await request.is_disconnected():
                break

            if event is None:
                # Keepalive tick — send SSE comment to prevent ALB idle timeout
                yield ": keepalive\n\n"
                continue

            event_user = event.get("user_id")
            if event_user and event_user != str(current_user.user.id):
                continue

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
