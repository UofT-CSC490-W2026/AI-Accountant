"""
Tax Service

Handles HST/GST tracking:
- Tax collected on sales (liability)
- Input Tax Credits (ITCs) on purchases (receivable)
- Net owing calculation per reporting period
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.enums import TaxObligationStatus, TaxType
from db.models.tax import TaxObligation


def get_or_create_tax_period(
    db: Session,
    user_id: uuid.UUID,
    tax_type: TaxType,
    period_start: date,
    period_end: date,
) -> TaxObligation:
    """
    Get or create a tax obligation period.

    Args:
        db: Database session.
        user_id: User ID.
        tax_type: Type of tax (HST, corporate income).
        period_start: Start of the reporting period.
        period_end: End of the reporting period.

    Returns:
        The existing or newly created TaxObligation.
    """
    stmt = select(TaxObligation).where(
        TaxObligation.user_id == user_id,
        TaxObligation.tax_type == tax_type,
        TaxObligation.period_start == period_start,
        TaxObligation.period_end == period_end,
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing is not None:
        return existing

    obligation = TaxObligation(
        user_id=user_id,
        tax_type=tax_type,
        period_start=period_start,
        period_end=period_end,
        amount_collected=Decimal("0"),
        itcs_claimed=Decimal("0"),
        net_owing=Decimal("0"),
        status=TaxObligationStatus.ACCRUING,
    )
    db.add(obligation)
    db.flush()
    return obligation


def record_tax_collected(
    db: Session,
    user_id: uuid.UUID,
    amount: Decimal,
    transaction_date: date,
    period_start: date,
    period_end: date,
) -> TaxObligation:
    """
    Record HST/GST collected on a sale.

    Args:
        db: Database session.
        user_id: User ID.
        amount: Tax amount collected.
        transaction_date: Date of the transaction.
        period_start: Start of the reporting period.
        period_end: End of the reporting period.

    Returns:
        The updated TaxObligation.
    """
    obligation = get_or_create_tax_period(
        db, user_id, TaxType.HST, period_start, period_end
    )

    obligation.amount_collected += amount
    obligation.net_owing = obligation.amount_collected - obligation.itcs_claimed

    db.flush()
    return obligation


def record_itc(
    db: Session,
    user_id: uuid.UUID,
    amount: Decimal,
    transaction_date: date,
    period_start: date,
    period_end: date,
) -> TaxObligation:
    """
    Record an Input Tax Credit (ITC) on a purchase.

    Args:
        db: Database session.
        user_id: User ID.
        amount: ITC amount.
        transaction_date: Date of the transaction.
        period_start: Start of the reporting period.
        period_end: End of the reporting period.

    Returns:
        The updated TaxObligation.
    """
    obligation = get_or_create_tax_period(
        db, user_id, TaxType.HST, period_start, period_end
    )

    obligation.itcs_claimed += amount
    obligation.net_owing = obligation.amount_collected - obligation.itcs_claimed

    db.flush()
    return obligation


def calculate_net_owing(
    db: Session,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> Decimal:
    """
    Calculate the net HST/GST owing for a period.

    Returns:
        Net amount owing (positive) or refund due (negative).
    """
    obligation = get_or_create_tax_period(
        db, user_id, TaxType.HST, period_start, period_end
    )
    return obligation.net_owing


def finalize_tax_period(
    db: Session,
    user_id: uuid.UUID,
    obligation_id: uuid.UUID,
) -> TaxObligation:
    """
    Mark a tax period as calculated (ready for filing).

    Args:
        db: Database session.
        user_id: User ID.
        obligation_id: ID of the tax obligation.

    Returns:
        The updated TaxObligation.
    """
    obligation = db.get(TaxObligation, obligation_id)
    if obligation is None:
        raise ValueError(f"Tax obligation {obligation_id} not found")

    if obligation.user_id != user_id:
        raise ValueError(f"Tax obligation {obligation_id} not owned by user")

    obligation.status = TaxObligationStatus.CALCULATED
    db.flush()
    return obligation


def record_tax_payment(
    db: Session,
    user_id: uuid.UUID,
    obligation_id: uuid.UUID,
    journal_entry_id: uuid.UUID,
) -> TaxObligation:
    """
    Record that a tax obligation has been paid.

    Args:
        db: Database session.
        user_id: User ID.
        obligation_id: ID of the tax obligation.
        journal_entry_id: ID of the payment journal entry.

    Returns:
        The updated TaxObligation.
    """
    obligation = db.get(TaxObligation, obligation_id)
    if obligation is None:
        raise ValueError(f"Tax obligation {obligation_id} not found")

    if obligation.user_id != user_id:
        raise ValueError(f"Tax obligation {obligation_id} not owned by user")

    obligation.status = TaxObligationStatus.PAID
    obligation.payment_journal_entry_id = journal_entry_id
    db.flush()
    return obligation


def list_tax_obligations(
    db: Session,
    user_id: uuid.UUID,
    tax_type: TaxType | None = None,
    status: TaxObligationStatus | None = None,
) -> list[TaxObligation]:
    """
    List tax obligations for a user.

    Args:
        db: Database session.
        user_id: User ID.
        tax_type: Optional filter by tax type.
        status: Optional filter by status.

    Returns:
        List of matching TaxObligation records.
    """
    stmt = select(TaxObligation).where(TaxObligation.user_id == user_id)

    if tax_type is not None:
        stmt = stmt.where(TaxObligation.tax_type == tax_type)

    if status is not None:
        stmt = stmt.where(TaxObligation.status == status)

    stmt = stmt.order_by(TaxObligation.period_end.desc())
    return list(db.execute(stmt).scalars().all())
