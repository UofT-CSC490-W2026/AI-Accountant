from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.account import ChartOfAccounts
    from app.models.asset import Asset
    from app.models.clarification import ClarificationTask
    from app.models.journal import JournalEntry
    from app.models.schedule import ScheduledEntry
    from app.models.transaction import Transaction


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

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
