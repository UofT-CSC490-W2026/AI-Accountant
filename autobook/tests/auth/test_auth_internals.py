from __future__ import annotations

import pytest
from fastapi import HTTPException

from auth.deps import (
    _extract_token,
    _parse_group_role,
    _parse_single_role,
    _resolve_role,
    _to_datetime,
)
from auth.schemas import TokenPayload, UserRole
from config import get_settings


def test_extract_token_from_bearer():
    token = _extract_token("Bearer abc123", None)
    assert token == "abc123"


def test_extract_token_from_query():
    token = _extract_token(None, "query-token")
    assert token == "query-token"


def test_extract_token_missing():
    with pytest.raises(HTTPException) as exc_info:
        _extract_token(None, None)
    assert exc_info.value.status_code == 401


def test_extract_token_malformed():
    with pytest.raises(HTTPException) as exc_info:
        _extract_token("Basic abc123", None)
    assert exc_info.value.status_code == 401


def test_parse_single_role_valid():
    assert _parse_single_role("manager") == UserRole.MANAGER


def test_parse_single_role_none():
    assert _parse_single_role(None) is None


def test_parse_single_role_unknown():
    assert _parse_single_role("admin") is None


def test_parse_group_role():
    result = _parse_group_role(["regular", "manager"])
    assert result == UserRole.MANAGER


def test_parse_group_role_empty():
    assert _parse_group_role([]) is None


def test_resolve_role_groups_first(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_ROLE_CLAIM_SOURCE", "cognito:groups")
    get_settings.cache_clear()

    claims = TokenPayload(
        sub="u1", exp=9999999999, iat=0, iss="test",
        token_use="access", cognito_groups=["manager"],
    )
    role, source = _resolve_role(claims)
    assert role == UserRole.MANAGER
    assert source == "cognito:groups"
    get_settings.cache_clear()


def test_resolve_role_custom_first(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_ROLE_CLAIM_SOURCE", "custom:role")
    get_settings.cache_clear()

    claims = TokenPayload(
        sub="u1", exp=9999999999, iat=0, iss="test",
        token_use="access", custom_role="superuser",
    )
    role, source = _resolve_role(claims)
    assert role == UserRole.SUPERUSER
    assert source == "custom:role"
    get_settings.cache_clear()


def test_resolve_role_default_fallback(monkeypatch):
    get_settings.cache_clear()
    claims = TokenPayload(
        sub="u1", exp=9999999999, iat=0, iss="test",
        token_use="access",
    )
    role, source = _resolve_role(claims)
    assert role == UserRole.REGULAR
    assert source == "default"
    get_settings.cache_clear()


def test_resolve_role_groups_then_custom_fallback(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("COGNITO_ROLE_CLAIM_SOURCE", "cognito:groups")
    get_settings.cache_clear()

    claims = TokenPayload(
        sub="u1", exp=9999999999, iat=0, iss="test",
        token_use="access", custom_role="superuser",
    )
    role, source = _resolve_role(claims)
    assert role == UserRole.SUPERUSER
    assert source == "custom:role"
    get_settings.cache_clear()


def test_to_datetime():
    from datetime import datetime, timezone
    result = _to_datetime(1700000000)
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc
