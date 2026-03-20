"""
Shareholder Loan Service

Tracks shareholder loan transactions and balances, with s.15(2) warning
for loans outstanding past fiscal year-end + one year.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.shareholder_loan import ShareholderLoanLedger


@dataclass
class ShareholderLoanWarning:
    """Warning for s.15(2) shareholder loan issues."""

    shareholder_name: str
    balance: Decimal
    oldest_debit_date: date
    deadline: date
    message: str


def record_shareholder_loan_transaction(
    db: Session,
    org_id: uuid.UUID,
    shareholder_name: str,
    transaction_date: date,
    amount: Decimal,
    description: str | None = None,
    journal_entry_id: uuid.UUID | None = None,
) -> ShareholderLoanLedger:
    """
    Record a shareholder loan transaction.

    Convention:
    - Positive amount: Company owes shareholder (shareholder loaned money to company)
    - Negative amount: Shareholder owes company (company paid personal expense, etc.)

    Args:
        db: Database session.
        org_id: Organization ID.
        shareholder_name: Name of the shareholder.
        transaction_date: Date of the transaction.
        amount: Transaction amount (positive = company owes, negative = shareholder owes).
        description: Optional description.
        journal_entry_id: Optional linked journal entry.

    Returns:
        The created ShareholderLoanLedger entry.
    """
    current_balance = get_shareholder_balance(db, org_id, shareholder_name)
    new_balance = current_balance + amount

    entry = ShareholderLoanLedger(
        org_id=org_id,
        shareholder_name=shareholder_name,
        transaction_date=transaction_date,
        amount=amount,
        description=description,
        journal_entry_id=journal_entry_id,
        running_balance=new_balance,
    )
    db.add(entry)
    db.flush()
    return entry


def get_shareholder_balance(
    db: Session,
    org_id: uuid.UUID,
    shareholder_name: str,
) -> Decimal:
    """
    Get the current balance for a shareholder.

    Returns:
        Current balance (positive = company owes, negative = shareholder owes).
    """
    stmt = (
        select(ShareholderLoanLedger.running_balance)
        .where(
            ShareholderLoanLedger.org_id == org_id,
            ShareholderLoanLedger.shareholder_name == shareholder_name,
        )
        .order_by(ShareholderLoanLedger.transaction_date.desc())
        .limit(1)
    )
    result = db.scalars(stmt).first()
    return result if result is not None else Decimal("0")


def get_all_shareholder_balances(
    db: Session,
    org_id: uuid.UUID,
) -> dict[str, Decimal]:
    """
    Get current balances for all shareholders.

    Returns:
        Dict mapping shareholder name to current balance.
    """
    subquery = (
        select(
            ShareholderLoanLedger.shareholder_name,
            func.max(ShareholderLoanLedger.transaction_date).label("max_date"),
        )
        .where(ShareholderLoanLedger.org_id == org_id)
        .group_by(ShareholderLoanLedger.shareholder_name)
        .subquery()
    )

    stmt = select(ShareholderLoanLedger).join(
        subquery,
        (ShareholderLoanLedger.shareholder_name == subquery.c.shareholder_name)
        & (ShareholderLoanLedger.transaction_date == subquery.c.max_date),
    )

    entries = db.scalars(stmt).all()
    return {entry.shareholder_name: entry.running_balance for entry in entries}


def get_shareholder_transactions(
    db: Session,
    org_id: uuid.UUID,
    shareholder_name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ShareholderLoanLedger]:
    """
    Get shareholder loan transactions with optional filters.

    Args:
        db: Database session.
        org_id: Organization ID.
        shareholder_name: Optional filter by shareholder.
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        List of ShareholderLoanLedger entries.
    """
    stmt = select(ShareholderLoanLedger).where(ShareholderLoanLedger.org_id == org_id)

    if shareholder_name is not None:
        stmt = stmt.where(ShareholderLoanLedger.shareholder_name == shareholder_name)

    if start_date is not None:
        stmt = stmt.where(ShareholderLoanLedger.transaction_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(ShareholderLoanLedger.transaction_date <= end_date)

    stmt = stmt.order_by(ShareholderLoanLedger.transaction_date)
    return list(db.scalars(stmt).all())


def check_s15_2_warning(
    db: Session,
    org_id: uuid.UUID,
    fiscal_year_end: date,
    check_date: date | None = None,
) -> list[ShareholderLoanWarning]:
    """
    Check for s.15(2) shareholder loan warnings.

    Under s.15(2) of the Income Tax Act, if a shareholder owes money to the
    corporation and the loan is not repaid by the end of the fiscal year
    following the year the loan was made, the amount is included in the
    shareholder's income.

    Args:
        db: Database session.
        org_id: Organization ID.
        fiscal_year_end: The corporation's fiscal year-end date.
        check_date: Date to check against (defaults to today).

    Returns:
        List of warnings for shareholders with outstanding loans.
    """
    from datetime import timedelta

    if check_date is None:
        check_date = date.today()

    warnings = []
    balances = get_all_shareholder_balances(db, org_id)

    for shareholder_name, balance in balances.items():
        if balance >= Decimal("0"):
            continue

        stmt = (
            select(func.min(ShareholderLoanLedger.transaction_date))
            .where(
                ShareholderLoanLedger.org_id == org_id,
                ShareholderLoanLedger.shareholder_name == shareholder_name,
                ShareholderLoanLedger.amount < 0,
            )
        )
        oldest_debit = db.scalars(stmt).first()

        if oldest_debit is None:
            continue

        loan_fiscal_year_end = date(
            oldest_debit.year if oldest_debit <= fiscal_year_end.replace(year=oldest_debit.year)
            else oldest_debit.year + 1,
            fiscal_year_end.month,
            fiscal_year_end.day,
        )
        deadline = loan_fiscal_year_end.replace(year=loan_fiscal_year_end.year + 1)

        days_until_deadline = (deadline - check_date).days

        if days_until_deadline <= 90:
            if days_until_deadline <= 0:
                message = (
                    f"URGENT: s.15(2) deadline has PASSED. "
                    f"${abs(balance):.2f} may be included in {shareholder_name}'s income."
                )
            else:
                message = (
                    f"WARNING: s.15(2) deadline in {days_until_deadline} days. "
                    f"${abs(balance):.2f} owed by {shareholder_name} must be repaid by {deadline}."
                )

            warnings.append(
                ShareholderLoanWarning(
                    shareholder_name=shareholder_name,
                    balance=balance,
                    oldest_debit_date=oldest_debit,
                    deadline=deadline,
                    message=message,
                )
            )

    return warnings
