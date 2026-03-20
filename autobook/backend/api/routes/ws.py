import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from queues import subscribe

logger = logging.getLogger(__name__)
router = APIRouter()

CHANNELS = ("entry.posted", "clarification.created", "clarification.resolved")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    redis = ws.app.state.redis
    try:
        async for event in subscribe(redis, *CHANNELS):
            await ws.send_json(event)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
