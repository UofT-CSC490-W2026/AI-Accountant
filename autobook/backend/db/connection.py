from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from db.credentials import get_database_url

engine = create_engine(get_database_url(), echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def set_current_user_context(db: Session, user_id: UUID | str) -> None:
    """Populate the PostgreSQL session variable used by RLS policies."""
    db.execute(
        text("select set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )
