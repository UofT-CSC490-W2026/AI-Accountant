from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, AuditMixin, Base
from app.models.enums import ReconciliationStatus

if TYPE_CHECKING:
    from app.models.journal import JournalEntry
    from app.models.organization import Organization


class ReconciliationRecord(AuditMixin, Base):
    __tablename__ = "reconciliation_records"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    bank_transaction_id: Mapped[str | None] = mapped_column(String(255))
    platform_transaction_ids: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(255))
    )
    status: Mapped[ReconciliationStatus]
    matched_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    discrepancy_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="reconciliation_records"
    )
    journal_entry: Mapped["JournalEntry | None"] = relationship("JournalEntry")
