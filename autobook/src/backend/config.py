from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    password_reset_token_ttl_minutes: int = 30
    password_reset_max_requests_per_hour: int = 3
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    default_regular_email: str = "user@example.com"
    default_regular_password: str = "RegularPass123!"
    default_manager_email: str = "manager@example.com"
    default_manager_password: str = "ManagerPass123!"
    default_superuser_email: str = "admin@example.com"
    default_superuser_password: str = "SuperuserPass123!"


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        secret_key=os.getenv("AUTOBOOK_SECRET_KEY", "dev-secret-key-change-me"),
        jwt_algorithm=os.getenv("AUTOBOOK_JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=_env_int("AUTOBOOK_ACCESS_TOKEN_EXPIRE_MINUTES", 15),
        password_reset_token_ttl_minutes=_env_int("AUTOBOOK_PASSWORD_RESET_TOKEN_TTL_MINUTES", 30),
        password_reset_max_requests_per_hour=_env_int("AUTOBOOK_PASSWORD_RESET_MAX_REQUESTS_PER_HOUR", 3),
        login_max_attempts=_env_int("AUTOBOOK_LOGIN_MAX_ATTEMPTS", 5),
        login_lockout_minutes=_env_int("AUTOBOOK_LOGIN_LOCKOUT_MINUTES", 15),
        default_regular_email=os.getenv("AUTOBOOK_DEFAULT_REGULAR_EMAIL", "user@example.com"),
        default_regular_password=os.getenv("AUTOBOOK_DEFAULT_REGULAR_PASSWORD", "RegularPass123!"),
        default_manager_email=os.getenv("AUTOBOOK_DEFAULT_MANAGER_EMAIL", "manager@example.com"),
        default_manager_password=os.getenv("AUTOBOOK_DEFAULT_MANAGER_PASSWORD", "ManagerPass123!"),
        default_superuser_email=os.getenv("AUTOBOOK_DEFAULT_SUPERUSER_EMAIL", "admin@example.com"),
        default_superuser_password=os.getenv("AUTOBOOK_DEFAULT_SUPERUSER_PASSWORD", "SuperuserPass123!"),
    )
