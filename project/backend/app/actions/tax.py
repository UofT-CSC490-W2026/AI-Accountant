from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError
from app.models.enums import TaxObligationStatus, TaxType
from app.models.tax import TaxObligation


class TaxDAO:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        org_id: uuid.UUID,
        tax_type: TaxType,
        period_start: date,
        period_end: date,
        amount_collected: Decimal = Decimal("0"),
        itcs_claimed: Decimal = Decimal("0"),
        net_owing: Decimal = Decimal("0"),
        status: TaxObligationStatus = TaxObligationStatus.ACCRUING,
        payment_journal_entry_id: uuid.UUID | None = None,
    ) -> TaxObligation:
        obligation = TaxObligation(
            org_id=org_id,
            tax_type=tax_type,
            period_start=period_start,
            period_end=period_end,
            amount_collected=amount_collected,
            itcs_claimed=itcs_claimed,
            net_owing=net_owing,
            status=status,
            payment_journal_entry_id=payment_journal_entry_id,
        )
        self._db.add(obligation)
        self._db.flush()
        return obligation

    def get(self, tax_obligation_id: uuid.UUID) -> TaxObligation:
        obligation = self._db.get(TaxObligation, tax_obligation_id)
        if obligation is None:
            raise NotFoundError(f"tax obligation {tax_obligation_id} not found")
        return obligation

    def mark_filed(self, *, tax_obligation_id: uuid.UUID) -> TaxObligation:
        obligation = self.get(tax_obligation_id)
        obligation.status = TaxObligationStatus.FILED
        self._db.flush()
        return obligation

    def mark_paid(
        self,
        *,
        tax_obligation_id: uuid.UUID,
        payment_journal_entry_id: uuid.UUID,
    ) -> TaxObligation:
        obligation = self.get(tax_obligation_id)
        obligation.status = TaxObligationStatus.PAID
        obligation.payment_journal_entry_id = payment_journal_entry_id
        self._db.flush()
        return obligation

    def calculate_hst_net_owing(
        self,
        *,
        org_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> dict:
        """Compute HST net owing for a period."""
        stmt = select(TaxObligation).where(
            TaxObligation.org_id == org_id,
            TaxObligation.tax_type == TaxType.HST,
            TaxObligation.period_start >= period_start,
            TaxObligation.period_end <= period_end,
        )
        obligations = list(self._db.execute(stmt).scalars().all())

        total_collected = sum(o.amount_collected for o in obligations)
        total_itcs = sum(o.itcs_claimed for o in obligations)
        net_owing = total_collected - total_itcs

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_collected": total_collected,
            "total_itcs": total_itcs,
            "net_owing": net_owing,
            "obligation_count": len(obligations),
        }

    def list(
        self,
        *,
        org_id: uuid.UUID,
        tax_type: TaxType | None = None,
        status: TaxObligationStatus | None = None,
    ) -> list[TaxObligation]:
        stmt = select(TaxObligation).where(TaxObligation.org_id == org_id)
        if tax_type is not None:
            stmt = stmt.where(TaxObligation.tax_type == tax_type)
        if status is not None:
            stmt = stmt.where(TaxObligation.status == status)
        stmt = stmt.order_by(TaxObligation.period_start)
        return list(self._db.execute(stmt).scalars().all())
