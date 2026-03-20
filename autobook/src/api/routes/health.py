from fastapi import APIRouter, Request

from schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    try:
        await request.app.state.redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return HealthResponse(status="ok", redis=redis_ok, db=False)
