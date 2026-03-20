from __future__ import annotations

from datetime import date

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base


class Organization(AuditMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    incorporation_date: Mapped[date | None]
    fiscal_year_end: Mapped[date]
    jurisdiction: Mapped[str] = mapped_column(String(50))
    hst_registration_number: Mapped[str | None] = mapped_column(String(50))
    business_number: Mapped[str | None] = mapped_column(String(20))

    # ── relationships ──────────────────────────────────────────────
    accounts: Mapped[list[ChartOfAccounts]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    journal_entries: Mapped[list[JournalEntry]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    assets: Mapped[list[Asset]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    shareholder_loans: Mapped[list[ShareholderLoanLedger]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    tax_obligations: Mapped[list[TaxObligation]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    corporate_documents: Mapped[list[CorporateDocument]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    scheduled_entries: Mapped[list[ScheduledEntry]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    integration_connections: Mapped[list[IntegrationConnection]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    reconciliation_records: Mapped[list[ReconciliationRecord]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
