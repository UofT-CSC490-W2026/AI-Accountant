from fastapi import FastAPI

from backend.routes.auth import router as auth_router
from backend.routes.health import router as health_router

app = FastAPI(title="Autobook API")
app.include_router(health_router)
app.include_router(auth_router)
