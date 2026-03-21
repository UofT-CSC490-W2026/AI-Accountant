from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("POSTGRES_DB", "ai_cfo")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app


TABLES = [
    "clarification_tasks",
    "journal_lines",
    "journal_entries",
    "transactions",
    "cca_schedule_entries",
    "assets",
    "scheduled_entries",
    "chart_of_accounts",
    "users",
]


@pytest.fixture()
def db_url() -> str:
    return (
        f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    )


@pytest.fixture(autouse=True)
def clean_database(db_url: str):
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("set session_replication_role = replica"))
        for table in TABLES:
            conn.execute(text(f"truncate table {table} cascade"))
        conn.execute(text("set session_replication_role = origin"))
    engine.dispose()
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
