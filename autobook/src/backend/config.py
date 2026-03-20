from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    cognito_region: str
    cognito_user_pool_id: str
    cognito_client_id: str | None
    cognito_jwks_json: str | None = None
    cognito_jwt_algorithm: str = "RS256"
    default_regular_email: str = "user@example.com"
    default_manager_email: str = "manager@example.com"
    default_superuser_email: str = "admin@example.com"

    @property
    def cognito_issuer(self) -> str:
        return f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"

    @property
    def cognito_jwks_url(self) -> str:
        return f"{self.cognito_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    region = os.getenv("AWS_REGION") or os.getenv("AUTOBOOK_COGNITO_REGION", "us-east-1")
    user_pool_id = os.getenv("COGNITO_POOL_ID") or os.getenv("AUTOBOOK_COGNITO_USER_POOL_ID", "local-test-pool")
    client_id = os.getenv("COGNITO_CLIENT_ID") or os.getenv("AUTOBOOK_COGNITO_CLIENT_ID", "local-test-client")
    return Settings(
        cognito_region=region,
        cognito_user_pool_id=user_pool_id,
        cognito_client_id=client_id,
        cognito_jwks_json=os.getenv("AUTOBOOK_COGNITO_JWKS_JSON"),
        cognito_jwt_algorithm=os.getenv("AUTOBOOK_COGNITO_JWT_ALGORITHM", "RS256"),
        default_regular_email=os.getenv("AUTOBOOK_DEFAULT_REGULAR_EMAIL", "user@example.com"),
        default_manager_email=os.getenv("AUTOBOOK_DEFAULT_MANAGER_EMAIL", "manager@example.com"),
        default_superuser_email=os.getenv("AUTOBOOK_DEFAULT_SUPERUSER_EMAIL", "admin@example.com"),
    )
