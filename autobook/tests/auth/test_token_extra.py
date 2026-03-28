from __future__ import annotations

import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from auth import token_service
from auth.mock_cognito import MockCognito, MockCognitoConfig
from config import get_settings

MOCK = MockCognito(MockCognitoConfig(region="us-east-1", user_pool_id="us-east-1_test", client_id="test-client", key_id="test-key"))


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    for key, value in MOCK.env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    token_service.clear_caches()


def test_decode_unknown_kid():
    mock2 = MockCognito(MockCognitoConfig(region="us-east-1", user_pool_id="us-east-1_test", client_id="test-client", key_id="unknown-kid"))
    token = mock2.issue_token(sub="u1", email="u@e.com")
    with pytest.raises(ValueError, match="key"):
        token_service.decode_access_token(token)


def test_decode_invalid_signature():
    token = MOCK.issue_token(sub="u1", email="u@e.com")
    parts = token.split(".")
    parts[2] = parts[2][::-1]  # corrupt signature
    corrupted = ".".join(parts)
    with pytest.raises(ValueError):
        token_service.decode_access_token(corrupted)


def test_decode_id_token_wrong_audience():
    token = MOCK.issue_token(sub="u1", email="u@e.com", token_use="id", client_id="wrong-aud")
    with pytest.raises(ValueError, match="client"):
        token_service.decode_access_token(token)
