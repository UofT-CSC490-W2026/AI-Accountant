from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.actions.errors import ActionError
from app.api.router import api_router

app = FastAPI(title="AI CFO", version="0.1.0")
app.include_router(api_router)


@app.exception_handler(ActionError)
def handle_action_error(_, exc: ActionError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValueError)
def handle_value_error(_, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
