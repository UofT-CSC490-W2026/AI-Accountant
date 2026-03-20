from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from queues import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = await get_redis(settings.REDIS_URL)
    yield
    await app.state.redis.aclose()


app = FastAPI(title="Autobook API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://ai-accountant490.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes.health import router as health_router
from api.routes.parse import router as parse_router
from api.routes.ledger import router as ledger_router
from api.routes.clarifications import router as clarifications_router
from api.routes.statements import router as statements_router
app.include_router(health_router)
app.include_router(parse_router)
app.include_router(ledger_router)
app.include_router(clarifications_router)
app.include_router(statements_router)
