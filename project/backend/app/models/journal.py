from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, AuditMixin, Base
from app.models.enums import JournalEntrySource, JournalEntryStatus


class JournalEntry(AuditMixin, Base):
    __tablename__ = "journal_entries"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    entry_date: Mapped[date]
    posted_date: Mapped[date | None]
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[JournalEntrySource] = mapped_column(
        default=JournalEntrySource.MANUAL
    )
    source_reference_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[JournalEntryStatus] = mapped_column(
        default=JournalEntryStatus.DRAFT
    )
    created_by: Mapped[str | None] = mapped_column(String(255))
    approved_by: Mapped[str | None] = mapped_column(String(255))

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped[Organization] = relationship(
        back_populates="journal_entries"
    )
    lines: Mapped[list[JournalEntryLine]] = relationship(
        back_populates="journal_entry",
        cascade="all, delete-orphan",
        order_by="JournalEntryLine.line_order",
    )


class JournalEntryLine(AuditMixin, Base):
    __tablename__ = "journal_entry_lines"
    __table_args__ = (
        CheckConstraint("debit_amount >= 0", name="ck_jel_debit_non_negative"),
        CheckConstraint("credit_amount >= 0", name="ck_jel_credit_non_negative"),
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) "
            "OR (debit_amount = 0 AND credit_amount > 0)",
            name="ck_jel_one_side_only",
        ),
    )

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chart_of_accounts.id"), index=True
    )
    debit_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    credit_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="CAD")
    description: Mapped[str | None] = mapped_column(Text)
    line_order: Mapped[int] = mapped_column(Integer, default=0)

    # ── relationships ──────────────────────────────────────────────
    journal_entry: Mapped[JournalEntry] = relationship(back_populates="lines")
    account: Mapped[ChartOfAccounts] = relationship(
        back_populates="journal_entry_lines"
    )
