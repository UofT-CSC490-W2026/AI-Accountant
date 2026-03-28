from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import Base

if TYPE_CHECKING:
    from db.models.transaction import Transaction
    from db.models.user import User


class ClarificationTask(Base):
    __tablename__ = "clarification_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    source_text: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    proposed_entry: Mapped[dict | None] = mapped_column(JSONB)
    evaluator_verdict: Mapped[str] = mapped_column(String(20))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="clarification_tasks")
    transaction: Mapped["Transaction"] = relationship(
        "Transaction", back_populates="clarification_tasks"
    )
