from __future__ import annotations

import pytest

from auth.mock_cognito import MockCognito
from auth.token_service import clear_caches, decode_access_token
from config import get_settings

MOCK = MockCognito()


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    for key, value in MOCK.env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    clear_caches()


def test_issue_token_groups():
    token = MOCK.issue_token(sub="user-1", groups=["manager"], email="mgr@example.com")
    payload = decode_access_token(token)
    assert "manager" in payload.cognito_groups


def test_issue_token_custom_role():
    token = MOCK.issue_token(sub="user-1", custom_role="admin")
    payload = decode_access_token(token)
    assert payload.custom_role == "admin"


def test_sample_tokens():
    tokens = MOCK.sample_tokens()
    assert "regular_access_token" in tokens
    assert "manager_access_token" in tokens
    assert "superuser_access_token" in tokens
    for token in tokens.values():
        payload = decode_access_token(token)
        assert payload.sub is not None
