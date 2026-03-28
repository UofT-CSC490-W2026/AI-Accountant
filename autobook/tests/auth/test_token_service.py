from __future__ import annotations

from datetime import timedelta

import pytest

from auth.mock_cognito import MockCognito
from auth.token_service import clear_caches, decode_access_token, _get_signing_key
from config import get_settings

MOCK = MockCognito()


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    for key, value in MOCK.env_vars.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    clear_caches()


def test_decode_valid_token():
    token = MOCK.issue_token(sub="user-1", email="user@example.com", groups=["regular"])
    payload = decode_access_token(token)
    assert payload.sub == "user-1"
    assert payload.token_use == "access"
    assert payload.email == "user@example.com"


def test_decode_expired_token():
    token = MOCK.issue_token(sub="user-1", expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="Token has expired"):
        decode_access_token(token)


def test_decode_wrong_issuer():
    token = MOCK.issue_token(sub="user-1", issuer="https://wrong-issuer.example.com")
    with pytest.raises(ValueError, match="Unexpected token issuer"):
        decode_access_token(token)


def test_decode_wrong_client_id():
    token = MOCK.issue_token(sub="user-1", client_id="wrong-client-id")
    with pytest.raises(ValueError, match="Unexpected Cognito app client"):
        decode_access_token(token)


def test_decode_wrong_token_use():
    token = MOCK.issue_token(sub="user-1", token_use="refresh")
    with pytest.raises(ValueError, match="Unsupported token use"):
        decode_access_token(token)


def test_decode_caches_jwks():
    clear_caches()
    token1 = MOCK.issue_token(sub="user-1")
    token2 = MOCK.issue_token(sub="user-2")
    decode_access_token(token1)
    decode_access_token(token2)
    assert _get_signing_key.cache_info().hits >= 1


def test_clear_caches():
    token = MOCK.issue_token(sub="user-1")
    decode_access_token(token)
    assert _get_signing_key.cache_info().currsize > 0
    clear_caches()
    assert _get_signing_key.cache_info().currsize == 0


def test_decode_malformed_token():
    with pytest.raises(ValueError, match="Malformed"):
        decode_access_token("not-a-jwt")


def test_decode_wrong_algorithm():
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "k1"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "u1", "token_use": "access"}).encode()).rstrip(b"=").decode()
    with pytest.raises(ValueError, match="(key|signature|Malformed)"):
        decode_access_token(f"{header}.{payload}.fakesig")


def test_decode_missing_kid():
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "u1", "token_use": "access"}).encode()).rstrip(b"=").decode()
    with pytest.raises(ValueError, match="key id"):
        decode_access_token(f"{header}.{payload}.fakesig")


def test_decode_id_token():
    token = MOCK.issue_token(sub="user-1", token_use="id", email="user@example.com")
    payload = decode_access_token(token)
    assert payload.sub == "user-1"
    assert payload.token_use == "id"


def test_decode_invalid_signature():
    token = MOCK.issue_token(sub="user-1")
    parts = token.split(".")
    corrupted = f"{parts[0]}.{parts[1]}.invalidsignature"
    with pytest.raises(ValueError, match="Malformed|Invalid"):
        decode_access_token(corrupted)


def test_decode_id_token_wrong_audience():
    token = MOCK.issue_token(sub="user-1", token_use="id", client_id="wrong-aud")
    with pytest.raises(ValueError, match="Unexpected Cognito app client"):
        decode_access_token(token)


def test_decode_unknown_kid():
    token = MOCK.issue_token(sub="user-1")
    parts = token.split(".")
    import base64, json
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    header["kid"] = "unknown-kid"
    new_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    with pytest.raises(ValueError, match="Unknown token key id"):
        decode_access_token(f"{new_header}.{parts[1]}.{parts[2]}")
