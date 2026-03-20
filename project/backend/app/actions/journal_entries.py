from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import ConflictError, NotFoundError, ValidationError
from app.models.enums import JournalEntrySource, JournalEntryStatus
from app.models.journal import JournalEntry, JournalEntryLine


def _to_decimal(value: object | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _validate_lines_balance(lines: list[JournalEntryLine]) -> None:
    debit_total = sum(_to_decimal(line.debit_amount) for line in lines)
    credit_total = sum(_to_decimal(line.credit_amount) for line in lines)
    if debit_total != credit_total:
        raise ValidationError(
            f"journal entry does not balance: debits={debit_total} credits={credit_total}"
        )


def _get_entry_lines(db: Session, entry_id: uuid.UUID) -> list[JournalEntryLine]:
    stmt = (
        select(JournalEntryLine)
        .where(JournalEntryLine.journal_entry_id == entry_id)
        .order_by(JournalEntryLine.line_order)
    )
    return list(db.execute(stmt).scalars().all())


# ── Create ───────────────────────────────────────────────────────


def create_journal_entry(
    db: Session,
    *,
    org_id: uuid.UUID,
    entry_date: date,
    description: str | None = None,
    source: JournalEntrySource = JournalEntrySource.MANUAL,
    source_reference_id: str | None = None,
    status: JournalEntryStatus = JournalEntryStatus.DRAFT,
    created_by: str | None = None,
    lines: list[dict],
) -> JournalEntry:
    """Create a journal entry with lines.

    Each line dict must contain ``account_id`` and exactly one of
    ``debit_amount`` or ``credit_amount``.  The entry must balance
    (total debits == total credits).
    """
    if not lines:
        raise ValidationError("journal entry must have at least one line")

    entry = JournalEntry(
        org_id=org_id,
        entry_date=entry_date,
        posted_date=None,
        description=description,
        source=source,
        source_reference_id=source_reference_id,
        status=status,
        created_by=created_by,
        approved_by=None,
    )
    db.add(entry)
    db.flush()

    jel_objects: list[JournalEntryLine] = []
    for idx, line in enumerate(lines):
        debit = _to_decimal(line.get("debit_amount"))
        credit = _to_decimal(line.get("credit_amount"))

        if debit > 0 and credit > 0:
            raise ValidationError(
                f"line {idx}: must have debit OR credit, not both"
            )
        if debit == 0 and credit == 0:
            raise ValidationError(
                f"line {idx}: must have a non-zero debit or credit"
            )
        if debit < 0 or credit < 0:
            raise ValidationError(
                f"line {idx}: amounts must be non-negative"
            )

        jel = JournalEntryLine(
            journal_entry_id=entry.id,
            account_id=line["account_id"],
            debit_amount=debit,
            credit_amount=credit,
            currency=line.get("currency", "CAD"),
            description=line.get("description"),
            line_order=line.get("line_order", idx),
        )
        jel_objects.append(jel)
        db.add(jel)

    db.flush()
    _validate_lines_balance(jel_objects)
    return entry


# ── Post ─────────────────────────────────────────────────────────


def post_journal_entry(
    db: Session,
    *,
    journal_entry_id: uuid.UUID,
    approved_by: str | None = None,
    posted_date: date | None = None,
) -> JournalEntry:
    """Transition a DRAFT or PENDING_REVIEW entry to POSTED.

    Re-validates balance before posting (§0.2 immutability rule).
    """
    entry = db.get(JournalEntry, journal_entry_id)
    if entry is None:
        raise NotFoundError(f"journal entry {journal_entry_id} not found")
    if entry.status == JournalEntryStatus.POSTED:
        return entry  # idempotent
    if entry.status == JournalEntryStatus.REVERSED:
        raise ConflictError("cannot post a reversed journal entry")

    lines = _get_entry_lines(db, entry.id)
    if not lines:
        raise ValidationError("journal entry has no lines")
    _validate_lines_balance(lines)

    entry.status = JournalEntryStatus.POSTED
    entry.approved_by = approved_by
    entry.posted_date = posted_date or entry.entry_date
    db.flush()
    return entry


# ── Submit for review ────────────────────────────────────────────


def submit_for_review(
    db: Session, *, journal_entry_id: uuid.UUID
) -> JournalEntry:
    """Move a DRAFT entry to PENDING_REVIEW."""
    entry = db.get(JournalEntry, journal_entry_id)
    if entry is None:
        raise NotFoundError(f"journal entry {journal_entry_id} not found")
    if entry.status != JournalEntryStatus.DRAFT:
        raise ConflictError(
            f"only draft entries can be submitted for review (current: {entry.status.value})"
        )
    entry.status = JournalEntryStatus.PENDING_REVIEW
    db.flush()
    return entry


# ── Reverse ──────────────────────────────────────────────────────


def reverse_journal_entry(
    db: Session,
    *,
    journal_entry_id: uuid.UUID,
    reversal_date: date,
    created_by: str | None = None,
    approved_by: str | None = None,
) -> JournalEntry:
    """Create a posted reversal entry with debits/credits swapped (§0.2).

    The original entry is marked REVERSED.
    """
    original = db.get(JournalEntry, journal_entry_id)
    if original is None:
        raise NotFoundError(f"journal entry {journal_entry_id} not found")
    if original.status != JournalEntryStatus.POSTED:
        raise ConflictError("only posted entries can be reversed")

    original_lines = _get_entry_lines(db, original.id)
    if not original_lines:
        raise ValidationError("original journal entry has no lines")

    reversal = JournalEntry(
        org_id=original.org_id,
        entry_date=reversal_date,
        posted_date=reversal_date,
        description=f"Reversal of: {original.description or str(original.id)}",
        source=JournalEntrySource.SYSTEM,
        source_reference_id=str(original.id),
        status=JournalEntryStatus.POSTED,
        created_by=created_by,
        approved_by=approved_by,
    )
    db.add(reversal)
    db.flush()

    reversal_lines: list[JournalEntryLine] = []
    for idx, line in enumerate(original_lines):
        new_line = JournalEntryLine(
            journal_entry_id=reversal.id,
            account_id=line.account_id,
            debit_amount=line.credit_amount,
            credit_amount=line.debit_amount,
            currency=line.currency,
            description=line.description,
            line_order=idx,
        )
        reversal_lines.append(new_line)
        db.add(new_line)

    db.flush()
    _validate_lines_balance(reversal_lines)

    original.status = JournalEntryStatus.REVERSED
    db.flush()
    return reversal


# ── Query helpers ────────────────────────────────────────────────


def get_journal_entry(db: Session, journal_entry_id: uuid.UUID) -> JournalEntry:
    entry = db.get(JournalEntry, journal_entry_id)
    if entry is None:
        raise NotFoundError(f"journal entry {journal_entry_id} not found")
    return entry


def list_journal_entries(
    db: Session,
    *,
    org_id: uuid.UUID,
    status: JournalEntryStatus | None = None,
) -> list[JournalEntry]:
    stmt = select(JournalEntry).where(JournalEntry.org_id == org_id)
    if status is not None:
        stmt = stmt.where(JournalEntry.status == status)
    stmt = stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    return list(db.execute(stmt).scalars().all())
