from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://autobook:autobook@localhost:5432/autobook"
    DB_SECRET_ARN: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    AWS_REGION: str | None = None
    AWS_DEFAULT_REGION: str = "ca-central-1"
    ENV: str = "local"
    AUTH_DEMO_MODE: bool = False
    COGNITO_USER_POOL_ID: str = Field(
        default="local-test-pool",
        validation_alias=AliasChoices("COGNITO_USER_POOL_ID", "COGNITO_POOL_ID"),
    )
    COGNITO_CLIENT_ID: str = "local-test-client"
    COGNITO_DOMAIN: str | None = None
    COGNITO_JWKS_JSON: str | None = None
    COGNITO_JWT_ALGORITHM: str = "RS256"
    COGNITO_ROLE_CLAIM_SOURCE: str = "cognito:groups"
    COGNITO_SCOPES: str = "openid email profile"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "https://autobook.tech",
        "https://www.autobook.tech",
        "https://ai-accountant490.netlify.app",
    ]
    AUTO_POST_THRESHOLD: float = 0.95  # confidence >= this → auto-post
    ML_INFERENCE_PROVIDER: str = "heuristic"
    ML_CLASSIFIER_MODEL_PATH: str | None = None
    ML_ENTITY_MODEL_PATH: str | None = None
    SQS_ENDPOINT_URL: str | None = None
    SQS_QUEUE_NORMALIZER: str = "http://elasticmq:9324/queue/normalizer"
    SQS_QUEUE_PRECEDENT: str = "http://elasticmq:9324/queue/precedent"
    SQS_QUEUE_ML_INFERENCE: str = "http://elasticmq:9324/queue/ml-inference"
    SQS_QUEUE_AGENT: str = "http://elasticmq:9324/queue/agent"
    SQS_QUEUE_RESOLUTION: str = "http://elasticmq:9324/queue/resolution"
    SQS_QUEUE_POSTING: str = "http://elasticmq:9324/queue/posting"
    SQS_QUEUE_FLYWHEEL: str = "http://elasticmq:9324/queue/flywheel"

    model_config = {"env_file": ".env", "case_sensitive": False}

    @property
    def cognito_region(self) -> str:
        return self.AWS_REGION or self.AWS_DEFAULT_REGION

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.COGNITO_USER_POOL_ID}"

    @property
    def cognito_jwks_url(self) -> str:
        return f"{self.cognito_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()

