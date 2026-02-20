from fastapi import FastAPI
from backend.routes.health import router as health_router

app = FastAPI(title="Autobook API")
app.include_router(health_router)
