from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base

if TYPE_CHECKING:
    from db.models.account import ChartOfAccounts
    from db.models.asset import Asset
    from db.models.auth_session import AuthSession
    from db.models.clarification import ClarificationTask
    from db.models.journal import JournalEntry
    from db.models.schedule import ScheduledEntry
    from db.models.transaction import Transaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cognito_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chart_of_accounts: Mapped[list["ChartOfAccounts"]] = relationship(
        "ChartOfAccounts", back_populates="user", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="user", cascade="all, delete-orphan"
    )
    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        "JournalEntry", back_populates="user", cascade="all, delete-orphan"
    )
    clarification_tasks: Mapped[list["ClarificationTask"]] = relationship(
        "ClarificationTask", back_populates="user", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        "Asset", back_populates="user", cascade="all, delete-orphan"
    )
    scheduled_entries: Mapped[list["ScheduledEntry"]] = relationship(
        "ScheduledEntry", back_populates="user", cascade="all, delete-orphan"
    )
    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        "AuthSession", back_populates="user", cascade="all, delete-orphan"
    )
