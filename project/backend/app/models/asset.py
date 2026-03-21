from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.journal import JournalEntry
    from app.models.user import User


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    acquisition_date: Mapped[date] = mapped_column(Date)
    acquisition_cost: Mapped[float] = mapped_column(Numeric(15, 2))
    cca_class: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="assets")
    cca_schedule_entries: Mapped[list["CCAScheduleEntry"]] = relationship(
        "CCAScheduleEntry", back_populates="asset", cascade="all, delete-orphan"
    )

    @property
    def org_id(self) -> uuid.UUID:
        return self.user_id


class CCAScheduleEntry(Base):
    __tablename__ = "cca_schedule_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer)
    ucc_opening: Mapped[float] = mapped_column(Numeric(15, 2))
    additions: Mapped[float] = mapped_column(Numeric(15, 2), default=0, server_default="0")
    dispositions: Mapped[float] = mapped_column(Numeric(15, 2), default=0, server_default="0")
    cca_claimed: Mapped[float] = mapped_column(Numeric(15, 2))
    ucc_closing: Mapped[float] = mapped_column(Numeric(15, 2))
    half_year_rule_applied: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped["Asset"] = relationship("Asset", back_populates="cca_schedule_entries")
    journal_entry: Mapped["JournalEntry | None"] = relationship("JournalEntry")
