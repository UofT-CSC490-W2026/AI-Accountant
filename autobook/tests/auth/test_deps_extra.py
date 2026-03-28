from __future__ import annotations

import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from auth.deps import _decode_bearer_token, _resolve_role
from auth.schemas import TokenPayload, UserRole
from auth.mock_cognito import MockCognito, MockCognitoConfig
from auth import token_service
from config import get_settings


MOCK = MockCognito(MockCognitoConfig(region="us-east-1", user_pool_id="us-east-1_test", client_id="test-client", key_id="test-key"))


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    for key, value in MOCK.env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    token_service.clear_caches()


def test_decode_demo_token_disabled():
    with pytest.raises(ValueError):
        _decode_bearer_token("demo:user@example.com")


def test_decode_demo_token_enabled(monkeypatch):
    monkeypatch.setenv("AUTH_DEMO_MODE", "true")
    get_settings.cache_clear()
    claims = _decode_bearer_token("demo:user@example.com")
    assert claims.sub == "demo:user@example.com"
    assert claims.email == "user@example.com"


def test_decode_demo_manager(monkeypatch):
    monkeypatch.setenv("AUTH_DEMO_MODE", "true")
    get_settings.cache_clear()
    claims = _decode_bearer_token("demo:manager@example.com")
    assert claims.cognito_groups == ["manager"]


def test_resolve_role_default():
    claims = TokenPayload(sub="u", exp=0, iat=0, iss="x", token_use="access")
    role, source = _resolve_role(claims)
    assert role == UserRole.REGULAR
    assert source == "default"


def test_resolve_role_custom_role_priority(monkeypatch):
    monkeypatch.setenv("COGNITO_ROLE_CLAIM_SOURCE", "custom:role")
    get_settings.cache_clear()
    claims = TokenPayload(sub="u", exp=0, iat=0, iss="x", token_use="access", **{"custom:role": "superuser"})
    role, source = _resolve_role(claims)
    assert role == UserRole.SUPERUSER
    assert source == "custom:role"


def test_resolve_role_custom_source_falls_to_group(monkeypatch):
    monkeypatch.setenv("COGNITO_ROLE_CLAIM_SOURCE", "custom:role")
    get_settings.cache_clear()
    claims = TokenPayload(sub="u", exp=0, iat=0, iss="x", token_use="access", **{"cognito:groups": ["manager"]})
    role, source = _resolve_role(claims)
    assert role == UserRole.MANAGER
    assert source == "cognito:groups"
