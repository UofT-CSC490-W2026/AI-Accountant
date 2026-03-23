"""
Double-Entry Accounting Engine

Core module that enforces accounting integrity:
- Every journal entry must balance (debits = credits)
- Posted entries are immutable; corrections via reversing entries
- Multi-currency support with functional currency (CAD) tracking
- Draft → Posted → Reversed workflow
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.enums import JournalEntrySource, JournalEntryStatus
from db.models.journal import JournalEntry, JournalLine
from services.actions.exceptions import (
    AccountNotFoundError,
    InvalidEntryStateError,
    UnbalancedEntryError,
)

if TYPE_CHECKING:
    from db.models.account import ChartOfAccounts


class JournalLineInput:
    """Input data for a single journal entry line."""

    def __init__(
        self,
        account_code: str,
        debit: Decimal = Decimal("0"),
        credit: Decimal = Decimal("0"),
        description: str | None = None,
        currency: str = "CAD",
    ):
        self.account_code = account_code
        self.debit = debit
        self.credit = credit
        self.description = description
        self.currency = currency


def validate_entry_balances(lines: list[JournalLineInput]) -> None:
    """
    Validate that total debits equal total credits.

    Raises:
        UnbalancedEntryError: If the entry does not balance.
    """
    total_debits = sum(line.debit for line in lines)
    total_credits = sum(line.credit for line in lines)

    if total_debits != total_credits:
        raise UnbalancedEntryError(
            f"Entry does not balance: debits={total_debits}, credits={total_credits}"
        )


def create_journal_entry(
    db: Session,
    user_id: uuid.UUID,
    entry_date: date,
    lines: list[JournalLineInput],
    description: str | None = None,
    source: JournalEntrySource = JournalEntrySource.MANUAL,
    source_reference_id: str | None = None,
    transaction_id: uuid.UUID | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Create a new journal entry with the given lines.

    Args:
        db: Database session.
        user_id: User ID who owns this entry.
        entry_date: Date of the transaction.
        lines: List of debit/credit lines (must balance).
        description: Optional description for the entry.
        source: Source of the entry (manual, stripe, etc.).
        source_reference_id: External reference ID (e.g., webhook event ID).
        transaction_id: Optional linked transaction.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.

    Raises:
        UnbalancedEntryError: If debits != credits.
        AccountNotFoundError: If any account_code does not exist.
    """
    from db.connection import set_current_user_context

    validate_entry_balances(lines)

    set_current_user_context(db, user_id)

    _validate_accounts_exist(db, user_id, [line.account_code for line in lines])

    status = JournalEntryStatus.POSTED if auto_post else JournalEntryStatus.DRAFT
    posted_at = datetime.now(timezone.utc) if auto_post else None

    entry = JournalEntry(
        user_id=user_id,
        transaction_id=transaction_id,
        date=entry_date,
        description=description or "",
        status=status,
        source=source.value if isinstance(source, JournalEntrySource) else source,
        source_reference_id=source_reference_id,
        posted_at=posted_at,
    )
    db.add(entry)
    db.flush()

    for i, line in enumerate(lines):
        if line.debit > 0:
            db_line = JournalLine(
                journal_entry_id=entry.id,
                account_code=line.account_code,
                account_name=_get_account_name(db, user_id, line.account_code),
                type="debit",
                amount=float(line.debit),
                line_order=i,
            )
            db.add(db_line)
        if line.credit > 0:
            db_line = JournalLine(
                journal_entry_id=entry.id,
                account_code=line.account_code,
                account_name=_get_account_name(db, user_id, line.account_code),
                type="credit",
                amount=float(line.credit),
                line_order=i + 1,
            )
            db.add(db_line)

    db.flush()
    return entry


def post_journal_entry(
    db: Session,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    posted_date: date | None = None,
) -> JournalEntry:
    """
    Post a draft journal entry, making it part of the official ledger.

    Args:
        db: Database session.
        user_id: User ID who owns this entry.
        entry_id: ID of the entry to post.
        posted_date: Date to record as posted (defaults to now).

    Returns:
        The updated JournalEntry.

    Raises:
        InvalidEntryStateError: If entry is not in DRAFT state.
    """
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not found")

    if entry.user_id != user_id:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not owned by user")

    if entry.status != JournalEntryStatus.DRAFT:
        raise InvalidEntryStateError(
            f"Cannot post entry in state {entry.status.value}"
        )

    entry.status = JournalEntryStatus.POSTED
    entry.posted_at = datetime.now(timezone.utc)

    db.flush()
    return entry


def reverse_journal_entry(
    db: Session,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    reversal_date: date,
    description: str | None = None,
) -> JournalEntry:
    """
    Create a reversing entry for a posted journal entry.

    This is the only way to "undo" a posted entry — we never modify posted entries.

    Args:
        db: Database session.
        user_id: User ID who owns this entry.
        entry_id: ID of the entry to reverse.
        reversal_date: Date for the reversing entry.
        description: Optional description (defaults to "Reversal of ...").

    Returns:
        The new reversing JournalEntry.

    Raises:
        InvalidEntryStateError: If entry is not POSTED.
    """
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    original = db.get(JournalEntry, entry_id)
    if original is None:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not found")

    if original.user_id != user_id:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not owned by user")

    if original.status != JournalEntryStatus.POSTED:
        raise InvalidEntryStateError(
            f"Can only reverse POSTED entries, not {original.status.value}"
        )

    reversal_lines = []
    for line in original.lines:
        if line.type == "debit":
            reversal_lines.append(
                JournalLineInput(
                    account_code=line.account_code,
                    credit=Decimal(str(line.amount)),
                    description=line.account_name,
                )
            )
        else:
            reversal_lines.append(
                JournalLineInput(
                    account_code=line.account_code,
                    debit=Decimal(str(line.amount)),
                    description=line.account_name,
                )
            )

    reversal_description = description or f"Reversal of entry {entry_id}"

    reversal = create_journal_entry(
        db=db,
        user_id=user_id,
        entry_date=reversal_date,
        lines=reversal_lines,
        description=reversal_description,
        source=JournalEntrySource.SYSTEM,
        source_reference_id=str(entry_id),
        auto_post=True,
    )

    original.status = JournalEntryStatus.REVERSED
    db.flush()

    return reversal


def get_account_balance(
    db: Session,
    user_id: uuid.UUID,
    account_code: str,
    as_of_date: date | None = None,
) -> Decimal:
    """
    Calculate the balance of an account as of a given date.

    For asset/expense accounts: balance = debits - credits
    For liability/equity/revenue accounts: balance = credits - debits

    Args:
        db: Database session.
        user_id: User ID who owns the account.
        account_code: The account code to query.
        as_of_date: Calculate balance up to this date (inclusive). None = all time.

    Returns:
        The account balance as a Decimal.
    """
    from db.connection import set_current_user_context
    from db.models.enums import AccountType

    set_current_user_context(db, user_id)

    account = db.execute(
        select(ChartOfAccounts).where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_code == account_code,
        )
    ).scalar_one_or_none()

    if account is None:
        raise AccountNotFoundError(f"Account {account_code} not found")

    query = (
        select(JournalLine)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .where(
            JournalLine.account_code == account_code,
            JournalEntry.user_id == user_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )

    if as_of_date is not None:
        query = query.where(JournalEntry.date <= as_of_date)

    lines = db.scalars(query).all()

    total_debits = sum(line.amount for line in lines if line.type == "debit")
    total_credits = sum(line.amount for line in lines if line.type == "credit")

    if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
        return Decimal(str(total_debits)) - Decimal(str(total_credits))
    else:
        return Decimal(str(total_credits)) - Decimal(str(total_debits))


def _validate_accounts_exist(
    db: Session, user_id: uuid.UUID, account_codes: list[str]
) -> None:
    """Validate that all account codes exist for the given user."""
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    for account_code in account_codes:
        account = db.execute(
            select(ChartOfAccounts).where(
                ChartOfAccounts.user_id == user_id,
                ChartOfAccounts.account_code == account_code,
            )
        ).scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(
                f"Account {account_code} not found for user"
            )


def _get_account_name(db: Session, user_id: uuid.UUID, account_code: str) -> str:
    """Get account name by account code."""
    from db.connection import set_current_user_context

    set_current_user_context(db, user_id)

    account = db.execute(
        select(ChartOfAccounts).where(
            ChartOfAccounts.user_id == user_id,
            ChartOfAccounts.account_code == account_code,
        )
    ).scalar_one_or_none()
    return account.account_name if account else account_code
