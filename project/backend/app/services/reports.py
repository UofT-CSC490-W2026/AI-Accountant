"""
Financial Reports

Generates standard financial statements:
- Trial Balance
- Balance Sheet
- Income Statement
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import ChartOfAccounts
from app.models.enums import AccountType, JournalEntryStatus
from app.models.journal import JournalEntry, JournalEntryLine


@dataclass
class AccountBalance:
    """A single account's balance for reporting."""

    account_id: uuid.UUID
    account_number: str
    account_name: str
    account_type: AccountType
    debit_balance: Decimal
    credit_balance: Decimal


@dataclass
class TrialBalance:
    """Trial balance report."""

    as_of_date: date
    accounts: list[AccountBalance]
    total_debits: Decimal
    total_credits: Decimal

    @property
    def is_balanced(self) -> bool:
        return self.total_debits == self.total_credits


@dataclass
class BalanceSheetSection:
    """A section of the balance sheet (e.g., Current Assets)."""

    name: str
    accounts: list[AccountBalance]
    total: Decimal


@dataclass
class BalanceSheet:
    """Balance sheet report."""

    as_of_date: date
    assets: list[BalanceSheetSection]
    liabilities: list[BalanceSheetSection]
    equity: list[BalanceSheetSection]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal

    @property
    def is_balanced(self) -> bool:
        return self.total_assets == (self.total_liabilities + self.total_equity)


@dataclass
class IncomeStatement:
    """Income statement (P&L) report."""

    period_start: date
    period_end: date
    revenue_accounts: list[AccountBalance]
    expense_accounts: list[AccountBalance]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


def generate_trial_balance(
    db: Session,
    org_id: uuid.UUID,
    as_of_date: date,
) -> TrialBalance:
    """
    Generate a trial balance as of a given date.

    Args:
        db: Database session.
        org_id: Organization ID.
        as_of_date: Date for the trial balance.

    Returns:
        TrialBalance report.
    """
    accounts = _get_all_accounts(db, org_id)
    balances = []

    for account in accounts:
        debit_total, credit_total = _get_account_totals(db, account.id, as_of_date)

        if debit_total == Decimal("0") and credit_total == Decimal("0"):
            continue

        if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            net = debit_total - credit_total
            debit_balance = net if net > 0 else Decimal("0")
            credit_balance = abs(net) if net < 0 else Decimal("0")
        else:
            net = credit_total - debit_total
            credit_balance = net if net > 0 else Decimal("0")
            debit_balance = abs(net) if net < 0 else Decimal("0")

        balances.append(
            AccountBalance(
                account_id=account.id,
                account_number=account.account_number,
                account_name=account.name,
                account_type=account.account_type,
                debit_balance=debit_balance,
                credit_balance=credit_balance,
            )
        )

    total_debits = sum(b.debit_balance for b in balances)
    total_credits = sum(b.credit_balance for b in balances)

    return TrialBalance(
        as_of_date=as_of_date,
        accounts=balances,
        total_debits=total_debits,
        total_credits=total_credits,
    )


def generate_balance_sheet(
    db: Session,
    org_id: uuid.UUID,
    as_of_date: date,
) -> BalanceSheet:
    """
    Generate a balance sheet as of a given date.

    Args:
        db: Database session.
        org_id: Organization ID.
        as_of_date: Date for the balance sheet.

    Returns:
        BalanceSheet report.
    """
    trial_balance = generate_trial_balance(db, org_id, as_of_date)

    asset_balances = [b for b in trial_balance.accounts if b.account_type == AccountType.ASSET]
    liability_balances = [b for b in trial_balance.accounts if b.account_type == AccountType.LIABILITY]
    equity_balances = [b for b in trial_balance.accounts if b.account_type == AccountType.EQUITY]

    assets_section = BalanceSheetSection(
        name="Assets",
        accounts=asset_balances,
        total=sum(b.debit_balance - b.credit_balance for b in asset_balances),
    )

    liabilities_section = BalanceSheetSection(
        name="Liabilities",
        accounts=liability_balances,
        total=sum(b.credit_balance - b.debit_balance for b in liability_balances),
    )

    equity_section = BalanceSheetSection(
        name="Equity",
        accounts=equity_balances,
        total=sum(b.credit_balance - b.debit_balance for b in equity_balances),
    )

    income_stmt = generate_income_statement(
        db, org_id, date(as_of_date.year, 1, 1), as_of_date
    )
    equity_section.total += income_stmt.net_income

    return BalanceSheet(
        as_of_date=as_of_date,
        assets=[assets_section],
        liabilities=[liabilities_section],
        equity=[equity_section],
        total_assets=assets_section.total,
        total_liabilities=liabilities_section.total,
        total_equity=equity_section.total,
    )


def generate_income_statement(
    db: Session,
    org_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> IncomeStatement:
    """
    Generate an income statement for a period.

    Args:
        db: Database session.
        org_id: Organization ID.
        period_start: Start of the period.
        period_end: End of the period.

    Returns:
        IncomeStatement report.
    """
    accounts = _get_all_accounts(db, org_id)

    revenue_balances = []
    expense_balances = []

    for account in accounts:
        debit_total, credit_total = _get_account_totals(
            db, account.id, period_end, period_start
        )

        if debit_total == Decimal("0") and credit_total == Decimal("0"):
            continue

        if account.account_type == AccountType.REVENUE:
            net = credit_total - debit_total
            balance = AccountBalance(
                account_id=account.id,
                account_number=account.account_number,
                account_name=account.name,
                account_type=account.account_type,
                debit_balance=Decimal("0"),
                credit_balance=net if net > 0 else Decimal("0"),
            )
            if net != Decimal("0"):
                revenue_balances.append(balance)

        elif account.account_type == AccountType.EXPENSE:
            net = debit_total - credit_total
            balance = AccountBalance(
                account_id=account.id,
                account_number=account.account_number,
                account_name=account.name,
                account_type=account.account_type,
                debit_balance=net if net > 0 else Decimal("0"),
                credit_balance=Decimal("0"),
            )
            if net != Decimal("0"):
                expense_balances.append(balance)

    total_revenue = sum(b.credit_balance for b in revenue_balances)
    total_expenses = sum(b.debit_balance for b in expense_balances)
    net_income = total_revenue - total_expenses

    return IncomeStatement(
        period_start=period_start,
        period_end=period_end,
        revenue_accounts=revenue_balances,
        expense_accounts=expense_balances,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_income=net_income,
    )


def _get_all_accounts(db: Session, org_id: uuid.UUID) -> list[ChartOfAccounts]:
    """Get all active accounts for an organization."""
    stmt = (
        select(ChartOfAccounts)
        .where(
            ChartOfAccounts.org_id == org_id,
            ChartOfAccounts.is_active == True,  # noqa: E712
        )
        .order_by(ChartOfAccounts.account_number)
    )
    return list(db.scalars(stmt).all())


def _get_account_totals(
    db: Session,
    account_id: uuid.UUID,
    as_of_date: date,
    start_date: date | None = None,
) -> tuple[Decimal, Decimal]:
    """
    Get total debits and credits for an account.

    Returns:
        Tuple of (total_debits, total_credits).
    """
    stmt = (
        select(JournalEntryLine)
        .join(JournalEntry)
        .where(
            JournalEntryLine.account_id == account_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.entry_date <= as_of_date,
        )
    )

    if start_date is not None:
        stmt = stmt.where(JournalEntry.entry_date >= start_date)

    lines = db.scalars(stmt).all()

    total_debits = sum(line.debit_amount for line in lines)
    total_credits = sum(line.credit_amount for line in lines)

    return total_debits, total_credits
