import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from auth.deps import resolve_auth_context_from_websocket
from db.connection import get_db
from queues import subscribe

logger = logging.getLogger(__name__)
router = APIRouter()

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, db: Session = Depends(get_db)):
    current_user = resolve_auth_context_from_websocket(ws, db)
    await ws.accept()
    redis = ws.app.state.redis
    try:
        async for event in subscribe(redis, *CHANNELS):
            event_user = event.get("user_id")
            if event_user and event_user != str(current_user.user.id):
                continue
            await ws.send_json(event)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
