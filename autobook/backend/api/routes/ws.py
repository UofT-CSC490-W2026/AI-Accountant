import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from queues import subscribe

logger = logging.getLogger(__name__)
router = APIRouter()

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    user_id = ws.query_params.get("userId")
    redis = ws.app.state.redis
    try:
        async for event in subscribe(redis, *CHANNELS):
            event_user = event.get("user_id")
            if user_id and event_user and event_user != user_id:
                continue
            await ws.send_json(event)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
