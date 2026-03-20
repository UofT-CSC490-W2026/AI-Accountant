from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://autobook:autobook@localhost:5432/autobook"
    REDIS_URL: str = "redis://localhost:6379/0"
    AWS_DEFAULT_REGION: str = "ca-central-1"
    ENV: str = "local"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    AUTO_POST_THRESHOLD: float = 0.95
    SQS_ENDPOINT_URL: str | None = None
    SQS_QUEUE_NORMALIZER: str = "http://elasticmq:9324/queue/normalizer"
    SQS_QUEUE_PRECEDENT: str = "http://elasticmq:9324/queue/precedent"
    SQS_QUEUE_ML_INFERENCE: str = "http://elasticmq:9324/queue/ml-inference"
    SQS_QUEUE_AGENT: str = "http://elasticmq:9324/queue/agent"
    SQS_QUEUE_RESOLUTION: str = "http://elasticmq:9324/queue/resolution"
    SQS_QUEUE_POSTING: str = "http://elasticmq:9324/queue/posting"
    SQS_QUEUE_FLYWHEEL: str = "http://elasticmq:9324/queue/flywheel"

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
