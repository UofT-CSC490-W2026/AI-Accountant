from __future__ import annotations

import json
from unittest.mock import Mock

from db.credentials import get_database_url


def test_get_database_url_env_var(monkeypatch):
    get_database_url.cache_clear()
    monkeypatch.delenv("DB_SECRET_ARN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
    result = get_database_url()
    assert result == "postgresql://test:test@localhost/testdb"
    get_database_url.cache_clear()


def test_get_database_url_cached(monkeypatch):
    get_database_url.cache_clear()
    monkeypatch.delenv("DB_SECRET_ARN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://cached@localhost/db")
    r1 = get_database_url()
    r2 = get_database_url()
    assert r1 is r2
    assert get_database_url.cache_info().hits >= 1
    get_database_url.cache_clear()


def test_get_database_url_ecs_construction(monkeypatch):
    get_database_url.cache_clear()
    monkeypatch.delenv("DB_SECRET_ARN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_USER", "ecs_user")
    monkeypatch.setenv("DB_PASSWORD", "ecs_pass")
    monkeypatch.setenv("DB_HOST", "rds.example.com")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "autobook")
    result = get_database_url()
    assert result == "postgresql://ecs_user:ecs_pass@rds.example.com:5432/autobook"
    get_database_url.cache_clear()


def test_get_database_url_from_secrets_manager(monkeypatch):
    get_database_url.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_SECRET_ARN", "arn:aws:secretsmanager:ca-central-1:123:secret:test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ca-central-1")

    secret_client = Mock()
    secret_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "autobook",
                "password": "secret",
                "host": "db.example",
                "port": 5432,
                "dbname": "autobook",
            }
        )
    }

    boto3_module = __import__("db.credentials", fromlist=["boto3"]).boto3
    monkeypatch.setattr(boto3_module, "client", Mock(return_value=secret_client))

    result = get_database_url()

    assert result == "postgresql://autobook:secret@db.example:5432/autobook"
    secret_client.get_secret_value.assert_called_once_with(
        SecretId="arn:aws:secretsmanager:ca-central-1:123:secret:test"
    )
    get_database_url.cache_clear()
