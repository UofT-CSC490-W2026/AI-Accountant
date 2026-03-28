from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.dao.chart_of_accounts import ChartOfAccountsDAO
from db.dao.journal_entries import JournalEntryDAO


@dataclass
class AccountSnapshot:
    account_code: str
    account_name: str
    account_type: str
    balance: Decimal


def _to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _to_float(value: Decimal) -> float:
    return float(value)


def _parse_as_of(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return date.today()


def _build_account_snapshots(db: Session, user_id, as_of: date) -> list[AccountSnapshot]:
    accounts = ChartOfAccountsDAO.list_by_user(db, user_id)
    entries = JournalEntryDAO.list_by_user(db, user_id, filters={"date_to": as_of, "status": "posted"})

    totals: dict[str, dict[str, Decimal]] = {
        account.account_code: {"debit": Decimal("0"), "credit": Decimal("0")}
        for account in accounts
    }

    for entry in entries:
        for line in entry.lines:
            bucket = totals.setdefault(
                line.account_code,
                {"debit": Decimal("0"), "credit": Decimal("0")},
            )
            bucket[line.type] += _to_decimal(line.amount)

    snapshots: list[AccountSnapshot] = []
    for account in accounts:
        bucket = totals.get(account.account_code, {"debit": Decimal("0"), "credit": Decimal("0")})
        debit_total = bucket["debit"]
        credit_total = bucket["credit"]
        if account.account_type in {"asset", "expense"}:
            balance = debit_total - credit_total
        else:
            balance = credit_total - debit_total
        snapshots.append(
            AccountSnapshot(
                account_code=account.account_code,
                account_name=account.account_name,
                account_type=account.account_type,
                balance=balance,
            )
        )
    return snapshots


def _rows_from_snapshots(snapshots: list[AccountSnapshot]) -> list[dict[str, float | str]]:
    return [
        {"label": snapshot.account_name, "amount": _to_float(snapshot.balance)}
        for snapshot in sorted(snapshots, key=lambda item: item.account_code)
        if snapshot.balance != 0
    ]


def build_balance_sheet(db: Session, user_id, as_of: str | None) -> dict:
    snapshot_date = _parse_as_of(as_of)
    snapshots = _build_account_snapshots(db, user_id, snapshot_date)

    assets = [item for item in snapshots if item.account_type == "asset"]
    liabilities = [item for item in snapshots if item.account_type == "liability"]
    equity = [item for item in snapshots if item.account_type == "equity"]
    revenues = [item for item in snapshots if item.account_type == "revenue"]
    expenses = [item for item in snapshots if item.account_type == "expense"]

    total_revenue = sum((item.balance for item in revenues), Decimal("0"))
    total_expenses = sum((item.balance for item in expenses), Decimal("0"))
    net_income = total_revenue - total_expenses

    equity_rows = _rows_from_snapshots(equity)
    if net_income != 0:
        equity_rows.append({"label": "Current Earnings", "amount": _to_float(net_income)})

    total_assets = sum((item.balance for item in assets), Decimal("0"))
    total_liabilities = sum((item.balance for item in liabilities), Decimal("0"))
    total_equity = sum((item.balance for item in equity), Decimal("0")) + net_income

    return {
        "statement_type": "balance_sheet",
        "period": {"as_of": snapshot_date.isoformat()},
        "sections": [
            {"title": "Assets", "rows": _rows_from_snapshots(assets)},
            {"title": "Liabilities", "rows": _rows_from_snapshots(liabilities)},
            {"title": "Equity", "rows": equity_rows},
        ],
        "totals": {
            "total_assets": _to_float(total_assets),
            "total_liabilities": _to_float(total_liabilities),
            "total_equity": _to_float(total_equity),
        },
    }


def build_income_statement(db: Session, user_id, as_of: str | None) -> dict:
    snapshot_date = _parse_as_of(as_of)
    snapshots = _build_account_snapshots(db, user_id, snapshot_date)

    revenues = [item for item in snapshots if item.account_type == "revenue"]
    expenses = [item for item in snapshots if item.account_type == "expense"]

    total_revenue = sum((item.balance for item in revenues), Decimal("0"))
    total_expenses = sum((item.balance for item in expenses), Decimal("0"))
    net_income = total_revenue - total_expenses

    return {
        "statement_type": "income_statement",
        "period": {"as_of": snapshot_date.isoformat()},
        "sections": [
            {"title": "Revenue", "rows": _rows_from_snapshots(revenues)},
            {"title": "Expenses", "rows": _rows_from_snapshots(expenses)},
        ],
        "totals": {
            "total_revenue": _to_float(total_revenue),
            "total_expenses": _to_float(total_expenses),
            "net_income": _to_float(net_income),
        },
    }


def build_trial_balance(db: Session, user_id, as_of: str | None) -> dict:
    snapshot_date = _parse_as_of(as_of)
    snapshots = _build_account_snapshots(db, user_id, snapshot_date)

    rows = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")

    for snapshot in sorted(snapshots, key=lambda item: item.account_code):
        if snapshot.balance == 0:
            continue
        debit = Decimal("0")
        credit = Decimal("0")
        if snapshot.account_type in {"asset", "expense"}:
            if snapshot.balance >= 0:
                debit = snapshot.balance
            else:
                credit = -snapshot.balance
        else:
            if snapshot.balance >= 0:
                credit = snapshot.balance
            else:
                debit = -snapshot.balance
        total_debits += debit
        total_credits += credit
        rows.append(
            {
                "label": f"{snapshot.account_code} {snapshot.account_name}",
                "amount": _to_float(debit if debit != 0 else credit),
            }
        )

    return {
        "statement_type": "trial_balance",
        "period": {"as_of": snapshot_date.isoformat()},
        "sections": [{"title": "Trial Balance", "rows": rows}],
        "totals": {
            "total_debits": _to_float(total_debits),
            "total_credits": _to_float(total_credits),
        },
    }
