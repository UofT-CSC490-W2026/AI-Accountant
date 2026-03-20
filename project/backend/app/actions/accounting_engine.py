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
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import JournalEntrySource, JournalEntryStatus
from app.models.journal import JournalEntry, JournalEntryLine
from app.services.exceptions import (
    AccountNotFoundError,
    InvalidEntryStateError,
    UnbalancedEntryError,
)

if TYPE_CHECKING:
    from app.models.account import ChartOfAccounts


class JournalLineInput:
    """Input data for a single journal entry line."""

    def __init__(
        self,
        account_id: uuid.UUID,
        debit: Decimal = Decimal("0"),
        credit: Decimal = Decimal("0"),
        description: str | None = None,
        currency: str = "CAD",
    ):
        self.account_id = account_id
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
    org_id: uuid.UUID,
    entry_date: date,
    lines: list[JournalLineInput],
    description: str | None = None,
    source: JournalEntrySource = JournalEntrySource.MANUAL,
    source_reference_id: str | None = None,
    created_by: str | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Create a new journal entry with the given lines.

    Args:
        db: Database session.
        org_id: Organization ID.
        entry_date: Date of the transaction.
        lines: List of debit/credit lines (must balance).
        description: Optional description for the entry.
        source: Source of the entry (manual, stripe, etc.).
        source_reference_id: External reference ID (e.g., webhook event ID).
        created_by: User or system that created the entry.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.

    Raises:
        UnbalancedEntryError: If debits != credits.
        AccountNotFoundError: If any account_id does not exist.
    """
    validate_entry_balances(lines)

    _validate_accounts_exist(db, org_id, [line.account_id for line in lines])

    entry = JournalEntry(
        org_id=org_id,
        entry_date=entry_date,
        description=description,
        source=source,
        source_reference_id=source_reference_id,
        status=JournalEntryStatus.DRAFT,
        created_by=created_by,
    )
    db.add(entry)
    db.flush()

    for i, line in enumerate(lines):
        db_line = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=line.account_id,
            debit_amount=line.debit,
            credit_amount=line.credit,
            currency=line.currency,
            description=line.description,
            line_order=i,
        )
        db.add(db_line)

    if auto_post:
        entry.status = JournalEntryStatus.POSTED
        entry.posted_date = entry_date

    db.flush()
    return entry


def post_journal_entry(
    db: Session,
    entry_id: uuid.UUID,
    posted_date: date | None = None,
    approved_by: str | None = None,
) -> JournalEntry:
    """
    Post a draft journal entry, making it part of the official ledger.

    Args:
        db: Database session.
        entry_id: ID of the entry to post.
        posted_date: Date to record as posted (defaults to entry_date).
        approved_by: User who approved the posting.

    Returns:
        The updated JournalEntry.

    Raises:
        InvalidEntryStateError: If entry is not in DRAFT or PENDING_REVIEW state.
    """
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not found")

    if entry.status not in (
        JournalEntryStatus.DRAFT,
        JournalEntryStatus.PENDING_REVIEW,
    ):
        raise InvalidEntryStateError(
            f"Cannot post entry in state {entry.status.value}"
        )

    entry.status = JournalEntryStatus.POSTED
    entry.posted_date = posted_date or entry.entry_date
    entry.approved_by = approved_by

    db.flush()
    return entry


def reverse_journal_entry(
    db: Session,
    entry_id: uuid.UUID,
    reversal_date: date,
    description: str | None = None,
    created_by: str | None = None,
) -> JournalEntry:
    """
    Create a reversing entry for a posted journal entry.

    This is the only way to "undo" a posted entry — we never modify posted entries.

    Args:
        db: Database session.
        entry_id: ID of the entry to reverse.
        reversal_date: Date for the reversing entry.
        description: Optional description (defaults to "Reversal of ...").
        created_by: User creating the reversal.

    Returns:
        The new reversing JournalEntry.

    Raises:
        InvalidEntryStateError: If entry is not POSTED.
    """
    original = db.get(JournalEntry, entry_id)
    if original is None:
        raise InvalidEntryStateError(f"Journal entry {entry_id} not found")

    if original.status != JournalEntryStatus.POSTED:
        raise InvalidEntryStateError(
            f"Can only reverse POSTED entries, not {original.status.value}"
        )

    reversal_lines = [
        JournalLineInput(
            account_id=line.account_id,
            debit=line.credit_amount,
            credit=line.debit_amount,
            description=line.description,
            currency=line.currency,
        )
        for line in original.lines
    ]

    reversal_description = description or f"Reversal of entry {entry_id}"

    reversal = create_journal_entry(
        db=db,
        org_id=original.org_id,
        entry_date=reversal_date,
        lines=reversal_lines,
        description=reversal_description,
        source=JournalEntrySource.SYSTEM,
        source_reference_id=str(entry_id),
        created_by=created_by,
        auto_post=True,
    )

    original.status = JournalEntryStatus.REVERSED
    db.flush()

    return reversal


def get_account_balance(
    db: Session,
    account_id: uuid.UUID,
    as_of_date: date | None = None,
) -> Decimal:
    """
    Calculate the balance of an account as of a given date.

    For asset/expense accounts: balance = debits - credits
    For liability/equity/revenue accounts: balance = credits - debits

    Args:
        db: Database session.
        account_id: The account to query.
        as_of_date: Calculate balance up to this date (inclusive). None = all time.

    Returns:
        The account balance as a Decimal.
    """
    from app.models.account import ChartOfAccounts
    from app.models.enums import AccountType

    account = db.get(ChartOfAccounts, account_id)
    if account is None:
        raise AccountNotFoundError(f"Account {account_id} not found")

    query = (
        select(JournalEntryLine)
        .join(JournalEntry)
        .where(
            JournalEntryLine.account_id == account_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        )
    )

    if as_of_date is not None:
        query = query.where(JournalEntry.entry_date <= as_of_date)

    lines = db.scalars(query).all()

    total_debits = sum(line.debit_amount for line in lines)
    total_credits = sum(line.credit_amount for line in lines)

    if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
        return total_debits - total_credits
    else:
        return total_credits - total_debits


def _validate_accounts_exist(
    db: Session, org_id: uuid.UUID, account_ids: list[uuid.UUID]
) -> None:
    """Validate that all account IDs exist for the given organization."""
    from app.models.account import ChartOfAccounts

    for account_id in account_ids:
        account = db.get(ChartOfAccounts, account_id)
        if account is None or account.org_id != org_id:
            raise AccountNotFoundError(
                f"Account {account_id} not found in organization {org_id}"
            )
