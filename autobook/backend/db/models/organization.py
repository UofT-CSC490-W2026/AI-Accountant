from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import AuditMixin, Base

if TYPE_CHECKING:
    from db.models.account import ChartOfAccounts
    from db.models.asset import Asset
    from db.models.document import CorporateDocument
    from db.models.integration import IntegrationConnection
    from db.models.journal import JournalEntry
    from db.models.reconciliation import ReconciliationRecord
    from db.models.schedule import ScheduledEntry
    from db.models.shareholder_loan import ShareholderLoanLedger
    from db.models.tax import TaxObligation


class Organization(AuditMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    incorporation_date: Mapped[date | None]
    fiscal_year_end: Mapped[date]
    jurisdiction: Mapped[str] = mapped_column(String(50))
    hst_registration_number: Mapped[str | None] = mapped_column(String(50))
    business_number: Mapped[str | None] = mapped_column(String(20))

    # ── relationships ──────────────────────────────────────────────
    shareholder_loans: Mapped[list["ShareholderLoanLedger"]] = relationship(
        "ShareholderLoanLedger",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    tax_obligations: Mapped[list["TaxObligation"]] = relationship(
        "TaxObligation", back_populates="organization", cascade="all, delete-orphan"
    )
    corporate_documents: Mapped[list["CorporateDocument"]] = relationship(
        "CorporateDocument", back_populates="organization", cascade="all, delete-orphan"
    )
    integration_connections: Mapped[list["IntegrationConnection"]] = relationship(
        "IntegrationConnection",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    reconciliation_records: Mapped[list["ReconciliationRecord"]] = relationship(
        "ReconciliationRecord",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
