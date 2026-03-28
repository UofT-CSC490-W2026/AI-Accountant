from __future__ import annotations

from local_identity import _parse_user_uuid, resolve_local_user


def test_parse_user_uuid_valid():
    import uuid
    u = uuid.uuid4()
    assert _parse_user_uuid(str(u)) == u


def test_parse_user_uuid_invalid():
    assert _parse_user_uuid("not-a-uuid") is None


def test_parse_user_uuid_none():
    assert _parse_user_uuid(None) is None


def test_parse_user_uuid_empty():
    assert _parse_user_uuid("") is None
