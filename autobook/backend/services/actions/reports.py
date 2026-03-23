"""Financial statement generation.

All reports query POSTED journal entries only. Amounts are returned as
dicts so they can be serialised to JSON by FastAPI without extra mapping.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func as F
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.account import ChartOfAccounts
from db.models.enums import AccountType, JournalEntryStatus
from db.models.journal import JournalEntry, JournalLine


def _account_balances(
    db: Session,
    *,
    user_id: uuid.UUID,
    as_of: date | None = None,
    account_types: list[AccountType] | None = None,
) -> list[dict]:
    """Return net balance per account (debits − credits for normal-debit
    accounts; credits − debits for normal-credit accounts).

    Returns a list of dicts with keys: account_id, account_code, account_name,
    account_type, sub_type, debit_total, credit_total, balance.
    """
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    stmt = (
        select(
            ChartOfAccounts.id,
            ChartOfAccounts.account_code,
            ChartOfAccounts.account_name,
            ChartOfAccounts.account_type,
            ChartOfAccounts.sub_type,
            F.coalesce(F.sum(JournalLine.amount), 0).label("debit_total"),
        )
        .select_from(ChartOfAccounts)
        .outerjoin(JournalLine, JournalLine.account_code == ChartOfAccounts.account_code)
        .outerjoin(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            ChartOfAccounts.user_id == user_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )
    if as_of is not None:
        stmt = stmt.where(JournalEntry.date <= as_of)
    if account_types is not None:
        stmt = stmt.where(ChartOfAccounts.account_type.in_(account_types))

    stmt = stmt.group_by(
        ChartOfAccounts.id,
        ChartOfAccounts.account_code,
        ChartOfAccounts.account_name,
        ChartOfAccounts.account_type,
        ChartOfAccounts.sub_type,
    ).order_by(ChartOfAccounts.account_code)

    rows = db.execute(stmt).all()

    stmt_credits = (
        select(
            JournalLine.account_code,
            F.coalesce(F.sum(JournalLine.amount), 0).label("credit_total"),
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            JournalLine.account_code.in_([r.account_code for r in rows]),
            JournalEntry.user_id == user_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalLine.type == "credit",
        )
        .group_by(JournalLine.account_code)
    )

    credit_map = {row.account_code: row.credit_total for row in db.execute(stmt_credits).all()}

    results: list[dict] = []
    for row in rows:
        debit_total = Decimal(str(row.debit_total or 0))
        credit_total = Decimal(str(credit_map.get(row.account_code, 0)))

        if row.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            balance = debit_total - credit_total
        else:
            balance = credit_total - debit_total

        results.append(
            {
                "account_id": str(row.id),
                "account_code": row.account_code,
                "account_name": row.account_name,
                "account_type": row.account_type.value,
                "sub_type": row.sub_type.value if row.sub_type else None,
                "debit_total": str(debit_total),
                "credit_total": str(credit_total),
                "balance": str(balance),
            }
        )
    return results


def trial_balance(
    db: Session,
    *,
    user_id: uuid.UUID,
    as_of: date | None = None,
) -> dict:
    """Generate a trial balance report.

    Returns a dict with ``accounts`` list and ``totals``.
    """
    accounts = _account_balances(db, user_id=user_id, as_of=as_of)

    total_debits = Decimal("0")
    total_credits = Decimal("0")
    for a in accounts:
        total_debits += Decimal(a["debit_total"])
        total_credits += Decimal(a["credit_total"])

    return {
        "as_of": as_of.isoformat() if as_of else None,
        "accounts": accounts,
        "total_debits": str(total_debits),
        "total_credits": str(total_credits),
        "balanced": total_debits == total_credits,
    }


def balance_sheet(
    db: Session,
    *,
    user_id: uuid.UUID,
    as_of: date | None = None,
) -> dict:
    """Generate a balance sheet (Assets = Liabilities + Equity)."""
    balances = _account_balances(
        db,
        user_id=user_id,
        as_of=as_of,
        account_types=[AccountType.ASSET, AccountType.LIABILITY, AccountType.EQUITY],
    )

    assets: list[dict] = []
    liabilities: list[dict] = []
    equity: list[dict] = []

    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    total_equity = Decimal("0")

    for a in balances:
        bal = Decimal(a["balance"])
        if a["account_type"] == AccountType.ASSET.value:
            assets.append(a)
            total_assets += bal
        elif a["account_type"] == AccountType.LIABILITY.value:
            liabilities.append(a)
            total_liabilities += bal
        else:
            equity.append(a)
            total_equity += bal

    return {
        "as_of": as_of.isoformat() if as_of else None,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": str(total_assets),
        "total_liabilities": str(total_liabilities),
        "total_equity": str(total_equity),
        "total_liabilities_and_equity": str(total_liabilities + total_equity),
        "balanced": total_assets == total_liabilities + total_equity,
    }


def income_statement(
    db: Session,
    *,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> dict:
    """Generate an income statement for a date range.

    Note: this queries entries with date in [start_date, end_date],
    so it only includes posted entries within the period.
    """
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    stmt = (
        select(
            ChartOfAccounts.id,
            ChartOfAccounts.account_code,
            ChartOfAccounts.account_name,
            ChartOfAccounts.account_type,
            ChartOfAccounts.sub_type,
            JournalLine.type,
            F.coalesce(F.sum(JournalLine.amount), 0).label("total"),
        )
        .select_from(ChartOfAccounts)
        .join(JournalLine, JournalLine.account_code == ChartOfAccounts.account_code)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_type.in_(
                [AccountType.REVENUE, AccountType.EXPENSE]
            ),
            JournalEntry.status == JournalEntryStatus.POSTED,
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date,
        )
        .group_by(
            ChartOfAccounts.id,
            ChartOfAccounts.account_code,
            ChartOfAccounts.account_name,
            ChartOfAccounts.account_type,
            ChartOfAccounts.sub_type,
            JournalLine.type,
        )
        .order_by(ChartOfAccounts.account_code)
    )

    rows = db.execute(stmt).all()

    account_totals: dict[str, dict] = {}
    for row in rows:
        key = row.account_code
        if key not in account_totals:
            account_totals[key] = {
                "account_id": str(row.id),
                "account_code": row.account_code,
                "account_name": row.account_name,
                "debit_total": Decimal("0"),
                "credit_total": Decimal("0"),
            }
        if row.type == "debit":
            account_totals[key]["debit_total"] += Decimal(str(row.total or 0))
        else:
            account_totals[key]["credit_total"] += Decimal(str(row.total or 0))

    revenues: list[dict] = []
    expenses: list[dict] = []
    total_revenue = Decimal("0")
    total_expenses = Decimal("0")

    for data in account_totals.values():
        debit_total = data["debit_total"]
        credit_total = data["credit_total"]

        if data["account_type"] == AccountType.REVENUE:
            balance = credit_total - debit_total
            total_revenue += balance
            revenues.append(
                {
                    "account_id": data["account_id"],
                    "account_code": data["account_code"],
                    "account_name": data["account_name"],
                    "balance": str(balance),
                }
            )
        else:
            balance = debit_total - credit_total
            total_expenses += balance
            expenses.append(
                {
                    "account_id": data["account_id"],
                    "account_code": data["account_code"],
                    "account_name": data["account_name"],
                    "balance": str(balance),
                }
            )

    net_income = total_revenue - total_expenses

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "revenues": revenues,
        "expenses": expenses,
        "total_revenue": str(total_revenue),
        "total_expenses": str(total_expenses),
        "net_income": str(net_income),
    }
