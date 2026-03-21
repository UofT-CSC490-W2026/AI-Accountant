from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.transaction import Transaction
    from app.models.user import User


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'posted')", name="ck_journal_entries_status"),
        CheckConstraint(
            "origin_tier IS NULL OR origin_tier BETWEEN 1 AND 4",
            name="ck_journal_entries_origin_tier",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.000 AND confidence <= 1.000)",
            name="ck_journal_entries_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    origin_tier: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="journal_entries")
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction", back_populates="journal_entries"
    )
    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine",
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalLine.line_order",
    )

    @property
    def entry_date(self) -> date:
        return self.date

    @entry_date.setter
    def entry_date(self, value: date) -> None:
        self.date = value

    @property
    def posted_date(self) -> date | None:
        return self.posted_at.date() if self.posted_at is not None else None


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("type IN ('debit', 'credit')", name="ck_journal_lines_type"),
        CheckConstraint("amount > 0", name="ck_journal_lines_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), index=True
    )
    account_code: Mapped[str] = mapped_column(String(20))
    account_name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))
    line_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    journal_entry: Mapped["JournalEntry"] = relationship(
        "JournalEntry", back_populates="lines"
    )


JournalEntryLine = JournalLine
