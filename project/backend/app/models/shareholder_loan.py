from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, AuditMixin, Base

if TYPE_CHECKING:
    from app.models.journal import JournalEntry
    from app.models.organization import Organization


class ShareholderLoanLedger(AuditMixin, Base):
    __tablename__ = "shareholder_loan_ledger"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    shareholder_name: Mapped[str] = mapped_column(String(255))
    transaction_date: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(MONEY)
    description: Mapped[str | None] = mapped_column(Text)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )
    running_balance: Mapped[Decimal] = mapped_column(MONEY)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="shareholder_loans"
    )
    journal_entry: Mapped["JournalEntry | None"] = relationship("JournalEntry")
