from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base

if TYPE_CHECKING:
    from db.models.clarification import ClarificationTask
    from db.models.journal import JournalEntry
    from db.models.user import User


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str] = mapped_column(Text)
    normalized_description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CAD", server_default="CAD")
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(50))
    counterparty: Mapped[str | None] = mapped_column(String(255))
    amount_mentions: Mapped[list[dict] | None] = mapped_column(JSONB)
    date_mentions: Mapped[list[dict] | None] = mapped_column(JSONB)
    party_mentions: Mapped[list[dict] | None] = mapped_column(JSONB)
    quantity_mentions: Mapped[list[dict] | None] = mapped_column(JSONB)
    intent_label: Mapped[str | None] = mapped_column(String(100))
    entities: Mapped[dict | None] = mapped_column(JSONB)
    bank_category: Mapped[str | None] = mapped_column(String(100))
    cca_class_match: Mapped[str | None] = mapped_column(String(50))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(
        "JournalEntry", back_populates="transaction"
    )
    clarification_tasks: Mapped[list["ClarificationTask"]] = relationship(
        "ClarificationTask", back_populates="transaction"
    )
