from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.actions.errors import ValidationError
from app.models.shareholder_loan import ShareholderLoanLedger


class ShareholderLoanDAO:
    def __init__(self, db: Session):
        self._db = db

    def _get_last_entry(
        self, *, org_id: uuid.UUID, shareholder_name: str
    ) -> ShareholderLoanLedger | None:
        stmt = (
            select(ShareholderLoanLedger)
            .where(
                ShareholderLoanLedger.org_id == org_id,
                ShareholderLoanLedger.shareholder_name == shareholder_name,
            )
            .order_by(
                desc(ShareholderLoanLedger.transaction_date),
                desc(ShareholderLoanLedger.created_at),
            )
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create_transaction(
        self,
        *,
        org_id: uuid.UUID,
        shareholder_name: str,
        transaction_date: date,
        amount: Decimal,
        description: str | None = None,
        journal_entry_id: uuid.UUID | None = None,
    ) -> ShareholderLoanLedger:
        """Record a shareholder loan transaction."""
        if not shareholder_name.strip():
            raise ValidationError("shareholder_name is required")

        last = self._get_last_entry(org_id=org_id, shareholder_name=shareholder_name)
        last_balance = last.running_balance if last is not None else Decimal("0")

        ledger = ShareholderLoanLedger(
            org_id=org_id,
            shareholder_name=shareholder_name,
            transaction_date=transaction_date,
            amount=amount,
            description=description,
            journal_entry_id=journal_entry_id,
            running_balance=last_balance + amount,
        )
        self._db.add(ledger)
        self._db.flush()
        return ledger

    def get_balance(self, *, org_id: uuid.UUID, shareholder_name: str) -> Decimal:
        """Return the current running balance for a shareholder."""
        last = self._get_last_entry(org_id=org_id, shareholder_name=shareholder_name)
        return last.running_balance if last is not None else Decimal("0")

    def check_section_15_2_warning(
        self,
        *,
        org_id: uuid.UUID,
        shareholder_name: str,
        fiscal_year_end: date,
    ) -> dict | None:
        """Check s.15(2) risk."""
        balance = self.get_balance(org_id=org_id, shareholder_name=shareholder_name)
        if balance >= 0:
            return None

        deadline = fiscal_year_end.replace(year=fiscal_year_end.year + 1)
        days_remaining = (deadline - date.today()).days

        if days_remaining <= 90:
            return {
                "shareholder_name": shareholder_name,
                "balance": balance,
                "deadline": deadline,
                "days_remaining": max(days_remaining, 0),
                "warning": (
                    f"Shareholder loan of {abs(balance)} to {shareholder_name} "
                    f"must be repaid by {deadline} to avoid s.15(2) inclusion in income."
                ),
            }
        return None

    def list_transactions(
        self,
        *,
        org_id: uuid.UUID,
        shareholder_name: str | None = None,
    ) -> list[ShareholderLoanLedger]:
        stmt = select(ShareholderLoanLedger).where(
            ShareholderLoanLedger.org_id == org_id
        )
        if shareholder_name is not None:
            stmt = stmt.where(
                ShareholderLoanLedger.shareholder_name == shareholder_name
            )
        stmt = stmt.order_by(
            ShareholderLoanLedger.transaction_date,
            ShareholderLoanLedger.created_at,
        )
        return list(self._db.execute(stmt).scalars().all())
