from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import MONEY, AuditMixin, Base
from db.models.enums import TaxObligationStatus, TaxType

if TYPE_CHECKING:
    from db.models.journal import JournalEntry
    from db.models.organization import Organization


class TaxObligation(AuditMixin, Base):
    __tablename__ = "tax_obligations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    tax_type: Mapped[TaxType]
    period_start: Mapped[date]
    period_end: Mapped[date]
    amount_collected: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    itcs_claimed: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    net_owing: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    status: Mapped[TaxObligationStatus] = mapped_column(
        default=TaxObligationStatus.ACCRUING
    )
    payment_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="tax_obligations"
    )
    payment_journal_entry: Mapped["JournalEntry | None"] = relationship(
        "JournalEntry"
    )
