from __future__ import annotations

from auth.deps import _extract_token, _parse_group_role, _parse_single_role, _to_datetime
from auth.schemas import UserRole

import pytest
from fastapi import HTTPException


def test_extract_token_bearer():
    assert _extract_token("Bearer abc123", None) == "abc123"


def test_extract_token_query():
    assert _extract_token(None, "tok-query") == "tok-query"


def test_extract_token_missing():
    with pytest.raises(HTTPException) as exc_info:
        _extract_token(None, None)
    assert exc_info.value.status_code == 401


def test_extract_token_malformed():
    with pytest.raises(HTTPException) as exc_info:
        _extract_token("Basic abc", None)
    assert exc_info.value.status_code == 401


def test_parse_single_role_valid():
    assert _parse_single_role("manager") == UserRole.MANAGER


def test_parse_single_role_none():
    assert _parse_single_role(None) is None


def test_parse_single_role_invalid():
    assert _parse_single_role("godmode") is None


def test_parse_group_role_highest():
    result = _parse_group_role(["regular", "manager"])
    assert result == UserRole.MANAGER


def test_parse_group_role_empty():
    assert _parse_group_role([]) is None


def test_parse_group_role_none():
    with pytest.raises(TypeError):
        _parse_group_role(None)


def test_to_datetime():
    dt = _to_datetime(1711152000)
    assert dt is not None
    assert dt.year >= 2024


def test_to_datetime_none():
    with pytest.raises(TypeError):
        _to_datetime(None)
