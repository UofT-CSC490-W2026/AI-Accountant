from __future__ import annotations

import os
import sys
from pathlib import Path

# Must be set before any backend module is imported (db/connection.py reads it at import time)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(element, compiler, **kw):
    return "JSON"


@pytest.fixture
def db_session():
    """Provide a fresh SQLite in-memory DB session for each test."""
    import db.models.user
    import db.models.account
    import db.models.transaction
    import db.models.journal
    import db.models.clarification
    import db.models.auth_session
    import db.models.asset
    import db.models.schedule
    import db.models.document
    import db.models.organization
    import db.models.reconciliation
    import db.models.tax
    import db.models.integration
    import db.models.shareholder_loan
    from db.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    yield session
    session.close()
