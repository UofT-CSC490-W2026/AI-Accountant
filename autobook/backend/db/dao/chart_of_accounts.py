from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from db.models.account import ChartOfAccounts

DEFAULT_COA: list[tuple[str, str, str]] = [
    ("1000", "Cash", "asset"),
    ("1100", "Accounts Receivable", "asset"),
    ("1200", "Prepaid Expenses", "asset"),
    ("1500", "Equipment", "asset"),
    ("9999", "Unknown Destination", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("2100", "HST/GST Payable", "liability"),
    ("2200", "Corporate Tax Payable", "liability"),
    ("2300", "Deferred Revenue", "liability"),
    ("2400", "Shareholder Loan", "liability"),
    ("3000", "Share Capital", "equity"),
    ("3100", "Retained Earnings", "equity"),
    ("4000", "Sales Revenue", "revenue"),
    ("4100", "Service Revenue", "revenue"),
    ("5000", "Cost of Goods Sold", "expense"),
    ("5200", "Rent Expense", "expense"),
    ("5300", "Software & Subscriptions", "expense"),
    ("5400", "Meals & Entertainment", "expense"),
    ("5430", "Professional Fees", "expense"),
    ("5500", "Bank Fees", "expense"),
    ("6200", "CCA Expense", "expense"),
]


class ChartOfAccountsDAO:
    @staticmethod
    def list_by_user(db: Session, user_id) -> list[ChartOfAccounts]:
        set_current_user_context(db, user_id)
        stmt = (
            select(ChartOfAccounts)
            .where(ChartOfAccounts.user_id == user_id)
            .order_by(ChartOfAccounts.account_code)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_by_code(db: Session, user_id, account_code: str) -> ChartOfAccounts | None:
        set_current_user_context(db, user_id)
        stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_code == account_code,
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_or_create(
        db: Session,
        user_id,
        account_code: str,
        account_name: str,
        account_type: str,
    ) -> ChartOfAccounts:
        existing = ChartOfAccountsDAO.get_by_code(db, user_id, account_code)
        if existing is not None:
            return existing

        account = ChartOfAccounts(
            user_id=user_id,
            account_code=account_code,
            account_name=account_name,
            account_type=account_type,
            auto_created=True,
        )
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def seed_defaults(db: Session, user_id) -> list[ChartOfAccounts]:
        set_current_user_context(db, user_id)
        seeded: list[ChartOfAccounts] = []
        for account_code, account_name, account_type in DEFAULT_COA:
            account = ChartOfAccountsDAO.get_by_code(db, user_id, account_code)
            if account is None:
                account = ChartOfAccounts(
                    user_id=user_id,
                    account_code=account_code,
                    account_name=account_name,
                    account_type=account_type,
                    auto_created=True,
                )
                db.add(account)
                db.flush()
            seeded.append(account)
        return seeded
