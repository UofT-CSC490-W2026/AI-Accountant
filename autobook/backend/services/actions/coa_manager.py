"""
Chart of Accounts Manager

Handles auto-creation of accounts and provides a standard Canadian small business
Chart of Accounts template. Accounts in the 5000 range (expenses) are lazily
instantiated when first referenced.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.account import ChartOfAccounts
from db.models.enums import AccountCreator, AccountSubType, AccountType
from services.actions.exceptions import AccountNotFoundError, DuplicateAccountError


@dataclass
class AccountTemplate:
    """Template for creating a standard account."""

    account_code: str
    account_name: str
    account_type: AccountType
    sub_type: AccountSubType | None = None


EXPENSE_TEMPLATES: dict[str, AccountTemplate] = {
    "rent": AccountTemplate("5200", "Rent Expense", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "utilities": AccountTemplate("5210", "Utilities", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "software": AccountTemplate("5300", "Software & Subscriptions", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "meals": AccountTemplate("5400", "Meals & Entertainment", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "travel": AccountTemplate("5410", "Travel Expense", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "office_supplies": AccountTemplate("5420", "Office Supplies", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "professional_fees": AccountTemplate("5500", "Professional Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "insurance": AccountTemplate("5510", "Insurance", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "advertising": AccountTemplate("5600", "Advertising & Marketing", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "bank_fees": AccountTemplate("5700", "Bank Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "stripe_fees": AccountTemplate("5710", "Payment Processing Fees", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "telephone": AccountTemplate("5220", "Telephone & Internet", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "repairs": AccountTemplate("5800", "Repairs & Maintenance", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "training": AccountTemplate("5810", "Training & Education", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
    "shipping": AccountTemplate("5820", "Shipping & Delivery", AccountType.EXPENSE, AccountSubType.OPERATING_EXPENSE),
}

DEFAULT_COA: list[AccountTemplate] = [
    AccountTemplate("1000", "Cash (Wise)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("1010", "Cash (Bank)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("1100", "Accounts Receivable", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("1200", "Prepaid Expenses", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("1300", "Inventory", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("1500", "Computer Equipment", AccountType.ASSET, AccountSubType.CCA_ASSET),
    AccountTemplate("1510", "Furniture & Equipment", AccountType.ASSET, AccountSubType.CCA_ASSET),
    AccountTemplate("1520", "Vehicles", AccountType.ASSET, AccountSubType.CCA_ASSET),
    AccountTemplate("1600", "Accumulated Depreciation", AccountType.ASSET, AccountSubType.FIXED_ASSET),
    AccountTemplate("2000", "Accounts Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("2100", "HST/GST Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("2150", "HST/GST Receivable (ITCs)", AccountType.ASSET, AccountSubType.CURRENT_ASSET),
    AccountTemplate("2200", "Corporate Tax Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("2300", "Deferred Revenue", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("2400", "Shareholder Loan", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("2500", "Loans Payable", AccountType.LIABILITY, AccountSubType.LONG_TERM_LIABILITY),
    AccountTemplate("2600", "Dividends Payable", AccountType.LIABILITY, AccountSubType.CURRENT_LIABILITY),
    AccountTemplate("3000", "Share Capital", AccountType.EQUITY, AccountSubType.SHARE_CAPITAL),
    AccountTemplate("3100", "Retained Earnings", AccountType.EQUITY, AccountSubType.RETAINED_EARNINGS),
    AccountTemplate("3200", "Dividends Declared", AccountType.EQUITY, AccountSubType.DIVIDENDS),
    AccountTemplate("4000", "Sales Revenue", AccountType.REVENUE, AccountSubType.SALES_REVENUE),
    AccountTemplate("4100", "Service Revenue", AccountType.REVENUE, AccountSubType.SERVICE_REVENUE),
    AccountTemplate("4200", "Interest Income", AccountType.REVENUE, AccountSubType.OTHER_INCOME),
    AccountTemplate("6000", "FX Gains/Losses", AccountType.EXPENSE, AccountSubType.OTHER_EXPENSE),
    AccountTemplate("6100", "Interest Expense", AccountType.EXPENSE, AccountSubType.OTHER_EXPENSE),
    AccountTemplate("6200", "CCA Expense", AccountType.EXPENSE, AccountSubType.CCA_EXPENSE),
]


def get_account_by_code(
    db: Session,
    user_id: uuid.UUID,
    account_code: str,
) -> ChartOfAccounts | None:
    """Look up an account by its account code within a user's accounts."""
    return db.execute(
        select(ChartOfAccounts).where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_code == account_code,
        )
    ).scalar_one_or_none()


def get_account_by_name(
    db: Session,
    user_id: uuid.UUID,
    account_name: str,
) -> ChartOfAccounts | None:
    """Look up an account by its name within a user's accounts."""
    return db.execute(
        select(ChartOfAccounts).where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_name == account_name,
        )
    ).scalar_one_or_none()


def create_account(
    db: Session,
    user_id: uuid.UUID,
    account_code: str,
    account_name: str,
    account_type: AccountType,
    sub_type: AccountSubType | None = None,
    parent_account_code: str | None = None,
    currency: str = "CAD",
    created_by: AccountCreator = AccountCreator.USER,
    auto_created: bool = False,
) -> ChartOfAccounts:
    """
    Create a new account in the Chart of Accounts.

    Raises:
        DuplicateAccountError: If account_code already exists for this user.
    """
    existing = get_account_by_code(db, user_id, account_code)
    if existing is not None:
        raise DuplicateAccountError(
            f"Account {account_code} already exists for user"
        )

    parent_account_id = None
    if parent_account_code:
        parent = get_account_by_code(db, user_id, parent_account_code)
        if parent:
            parent_account_id = parent.id

    account = ChartOfAccounts(
        user_id=user_id,
        account_code=account_code,
        account_name=account_name,
        account_type=account_type,
        sub_type=sub_type,
        parent_account_id=parent_account_id,
        currency=currency,
        created_by=created_by,
        auto_created=auto_created,
    )
    db.add(account)
    db.flush()
    return account


def get_or_create_expense_account(
    db: Session,
    user_id: uuid.UUID,
    category: str,
) -> ChartOfAccounts:
    """
    Get an expense account by category, creating it if it doesn't exist.

    This is the lazy instantiation mechanism for expense accounts.

    Args:
        db: Database session.
        user_id: User ID.
        category: Expense category key (e.g., "rent", "software", "meals").

    Returns:
        The existing or newly created account.

    Raises:
        AccountNotFoundError: If category is not in EXPENSE_TEMPLATES.
    """
    template = EXPENSE_TEMPLATES.get(category.lower())
    if template is None:
        raise AccountNotFoundError(
            f"Unknown expense category: {category}. "
            f"Valid categories: {list(EXPENSE_TEMPLATES.keys())}"
        )

    existing = get_account_by_code(db, user_id, template.account_code)
    if existing is not None:
        return existing

    return create_account(
        db=db,
        user_id=user_id,
        account_code=template.account_code,
        account_name=template.account_name,
        account_type=template.account_type,
        sub_type=template.sub_type,
        created_by=AccountCreator.SYSTEM,
        auto_created=True,
    )


def create_default_chart_of_accounts(
    db: Session,
    user_id: uuid.UUID,
) -> list[ChartOfAccounts]:
    """
    Create the standard Chart of Accounts for a new user.

    This creates all the default accounts (assets, liabilities, equity, revenue,
    and core expense accounts). Additional expense accounts are created lazily
    via get_or_create_expense_account().

    Returns:
        List of created accounts.
    """
    accounts = []
    for template in DEFAULT_COA:
        existing = get_account_by_code(db, user_id, template.account_code)
        if existing is not None:
            accounts.append(existing)
            continue

        account = create_account(
            db=db,
            user_id=user_id,
            account_code=template.account_code,
            account_name=template.account_name,
            account_type=template.account_type,
            sub_type=template.sub_type,
            created_by=AccountCreator.SYSTEM,
            auto_created=False,
        )
        accounts.append(account)

    db.flush()
    return accounts


def list_accounts(
    db: Session,
    user_id: uuid.UUID,
    account_type: AccountType | None = None,
    active_only: bool = True,
) -> list[ChartOfAccounts]:
    """
    List all accounts for a user, optionally filtered.

    Args:
        db: Database session.
        user_id: User ID.
        account_type: Filter by account type (optional).
        active_only: If True, only return active accounts.

    Returns:
        List of matching accounts, ordered by account_code.
    """
    stmt = select(ChartOfAccounts).where(ChartOfAccounts.user_id == user_id)

    if account_type is not None:
        stmt = stmt.where(ChartOfAccounts.account_type == account_type)

    if active_only:
        stmt = stmt.where(ChartOfAccounts.is_active == True)  # noqa: E712

    stmt = stmt.order_by(ChartOfAccounts.account_code)
    return list(db.execute(stmt).scalars().all())
