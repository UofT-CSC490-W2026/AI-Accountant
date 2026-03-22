from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError, ValidationError
from app.models.account import ChartOfAccounts
from app.models.enums import AccountCreator, AccountSubType, AccountType


# ── Full Canadian Small-Business CoA Template (§0.3) ─────────────
# Each tuple: (account_number, name, account_type, sub_type)

SEED_ACCOUNTS: list[tuple[str, str, AccountType, AccountSubType]] = [
    # Assets 1000–1999
    ("1000", "Cash (Wise)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("1010", "Cash (Bank - via Plaid)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("1100", "Accounts Receivable (Stripe)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("1200", "Prepaid Expenses", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("1300", "Inventory", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("1500", "Computer Equipment (CCA Class 50)", AccountType.ASSET, AccountSubType.CCA_ASSET),
    ("1510", "Furniture & Equipment (CCA Class 8)", AccountType.ASSET, AccountSubType.CCA_ASSET),
    ("1520", "Vehicles (CCA Class 10/10.1)", AccountType.ASSET, AccountSubType.CCA_ASSET),
    # Liabilities 2000–2999
    ("2000", "Accounts Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    ("2100", "HST/GST Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    ("2150", "HST/GST Receivable (ITCs)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    ("2200", "Corporate Tax Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    ("2300", "Deferred Revenue", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    ("2400", "Shareholder Loan", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    ("2500", "Loans Payable", AccountType.LIABILITY, AccountSubType.LONG_TERM_LIABILITY),
    # Equity 3000–3999
    ("3000", "Share Capital", AccountType.EQUITY, AccountSubType.SHARE_CAPITAL),
    ("3100", "Retained Earnings", AccountType.EQUITY, AccountSubType.RETAINED_EARNINGS),
    ("3200", "Dividends Declared", AccountType.EQUITY, AccountSubType.DIVIDENDS),
    # Revenue 4000–4999
    ("4000", "Sales Revenue", AccountType.REVENUE, AccountSubType.SALES_REVENUE),
    ("4100", "Service Revenue", AccountType.REVENUE, AccountSubType.SERVICE_REVENUE),
    # Other 6000–6999
    ("6000", "FX Gains/Losses", AccountType.EXPENSE, AccountSubType.OTHER_EXPENSE),
    ("6100", "Interest Expense", AccountType.EXPENSE, AccountSubType.OTHER_EXPENSE),
    ("6200", "CCA Expense", AccountType.EXPENSE, AccountSubType.CCA_EXPENSE),
]


# ── Lazy-creation template map for 5000-range expense accounts (§0.4) ──

EXPENSE_TEMPLATE_MAP: dict[str, tuple[str, str, AccountType, AccountSubType]] = {
    "rent": ("5200", "Rent Expense", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "utilities": ("5210", "Utilities", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "software": ("5300", "Software & Subscriptions", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "meals": ("5400", "Meals & Entertainment", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "travel": ("5410", "Travel", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "office_supplies": ("5420", "Office Supplies", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "professional_fees": ("5430", "Professional Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "insurance": ("5440", "Insurance", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "bank_fee": ("5500", "Bank Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "stripe_fee": ("5510", "Stripe Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "cogs": ("5000", "Cost of Goods Sold", AccountType.EXPENSE, AccountSubType.COST_OF_GOODS_SOLD),
}


# ── DAO ─────────────────────────────────────────────────────────


class AccountDAO:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        org_id: uuid.UUID,
        account_number: str,
        name: str,
        account_type: AccountType,
        sub_type: AccountSubType | None = None,
        parent_account_id: uuid.UUID | None = None,
        currency: str = "CAD",
        is_active: bool = True,
        created_by: AccountCreator = AccountCreator.USER,
        auto_created: bool = False,
    ) -> ChartOfAccounts:
        account = ChartOfAccounts(
            org_id=org_id,
            account_number=account_number,
            name=name,
            account_type=account_type,
            sub_type=sub_type,
            parent_account_id=parent_account_id,
            currency=currency,
            is_active=is_active,
            created_by=created_by,
            auto_created=auto_created,
        )
        self._db.add(account)
        self._db.flush()
        return account

    def get(self, account_id: uuid.UUID) -> ChartOfAccounts:
        account = self._db.get(ChartOfAccounts, account_id)
        if account is None:
            raise NotFoundError(f"account {account_id} not found")
        return account

    def get_by_number(self, *, org_id: uuid.UUID, account_number: str) -> ChartOfAccounts | None:
        stmt = select(ChartOfAccounts).where(
            ChartOfAccounts.org_id == org_id,
            ChartOfAccounts.account_number == account_number,
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def list(self, *, org_id: uuid.UUID, active_only: bool = True) -> list[ChartOfAccounts]:
        stmt = select(ChartOfAccounts).where(ChartOfAccounts.org_id == org_id)
        if active_only:
            stmt = stmt.where(ChartOfAccounts.is_active.is_(True))
        stmt = stmt.order_by(ChartOfAccounts.account_number)
        return list(self._db.execute(stmt).scalars().all())

    def get_or_create(
        self,
        *,
        org_id: uuid.UUID,
        category: str,
        currency: str = "CAD",
    ) -> ChartOfAccounts:
        """Lazy-create an expense account from the template map."""
        template = EXPENSE_TEMPLATE_MAP.get(category)
        if template is None:
            raise ValidationError(f"unknown expense category: {category!r}")

        account_number, name, account_type, sub_type = template

        existing = self.get_by_number(org_id=org_id, account_number=account_number)
        if existing is not None:
            return existing

        return self.create(
            org_id=org_id,
            account_number=account_number,
            name=name,
            account_type=account_type,
            sub_type=sub_type,
            currency=currency,
            created_by=AccountCreator.SYSTEM,
            auto_created=True,
        )

    def seed(self, *, org_id: uuid.UUID) -> list[ChartOfAccounts]:
        """Create the standard Canadian small-business CoA for a new org (§0.3).

        Skips any accounts that already exist (idempotent).
        """
        created: list[ChartOfAccounts] = []
        for acct_num, name, acct_type, sub_type in SEED_ACCOUNTS:
            existing = self.get_by_number(org_id=org_id, account_number=acct_num)
            if existing is not None:
                created.append(existing)
                continue
            account = self.create(
                org_id=org_id,
                account_number=acct_num,
                name=name,
                account_type=acct_type,
                sub_type=sub_type,
                created_by=AccountCreator.SYSTEM,
                auto_created=True,
            )
            created.append(account)
        return created
