from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, AuditMixin, Base
from app.models.enums import AssetStatus

if TYPE_CHECKING:
    from app.models.journal import JournalEntry
    from app.models.organization import Organization


class Asset(AuditMixin, Base):
    __tablename__ = "assets"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    acquisition_date: Mapped[date]
    acquisition_cost: Mapped[Decimal] = mapped_column(MONEY)
    cca_class: Mapped[str | None] = mapped_column(String(10))
    cca_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    disposition_date: Mapped[date | None]
    disposition_proceeds: Mapped[Decimal | None] = mapped_column(MONEY)
    book_depreciation_method: Mapped[str | None] = mapped_column(String(50))
    book_useful_life: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[AssetStatus] = mapped_column(default=AssetStatus.ACTIVE)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="assets"
    )
    cca_schedule_entries: Mapped[list["CCAScheduleEntry"]] = relationship(
        "CCAScheduleEntry", back_populates="asset", cascade="all, delete-orphan"
    )


class CCAScheduleEntry(AuditMixin, Base):
    __tablename__ = "cca_schedule_entries"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer)
    ucc_opening: Mapped[Decimal] = mapped_column(MONEY)
    additions: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    dispositions: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    cca_claimed: Mapped[Decimal] = mapped_column(MONEY)
    ucc_closing: Mapped[Decimal] = mapped_column(MONEY)
    half_year_rule_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    aiip_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    # ── relationships ──────────────────────────────────────────────
    asset: Mapped["Asset"] = relationship(
        "Asset", back_populates="cca_schedule_entries"
    )
    journal_entry: Mapped["JournalEntry | None"] = relationship("JournalEntry")
