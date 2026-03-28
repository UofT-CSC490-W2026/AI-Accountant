from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    redis: bool
    db: bool
