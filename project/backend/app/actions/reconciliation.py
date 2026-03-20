from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError
from app.models.enums import ReconciliationStatus
from app.models.reconciliation import ReconciliationRecord


def create_reconciliation_record(
    db: Session,
    *,
    org_id: uuid.UUID,
    bank_transaction_id: str | None = None,
    platform_transaction_ids: list[str] | None = None,
    status: ReconciliationStatus,
    matched_amount: Decimal | None = None,
    discrepancy_amount: Decimal | None = None,
    journal_entry_id: uuid.UUID | None = None,
) -> ReconciliationRecord:
    rec = ReconciliationRecord(
        org_id=org_id,
        bank_transaction_id=bank_transaction_id,
        platform_transaction_ids=platform_transaction_ids,
        status=status,
        matched_amount=matched_amount,
        discrepancy_amount=discrepancy_amount,
        journal_entry_id=journal_entry_id,
    )
    db.add(rec)
    db.flush()
    return rec


def confirm_reconciliation(
    db: Session, *, record_id: uuid.UUID
) -> ReconciliationRecord:
    rec = db.get(ReconciliationRecord, record_id)
    if rec is None:
        raise NotFoundError(f"reconciliation record {record_id} not found")
    rec.status = ReconciliationStatus.USER_CONFIRMED
    db.flush()
    return rec


def list_reconciliation_records(
    db: Session,
    *,
    org_id: uuid.UUID,
    status: ReconciliationStatus | None = None,
) -> list[ReconciliationRecord]:
    stmt = select(ReconciliationRecord).where(
        ReconciliationRecord.org_id == org_id
    )
    if status is not None:
        stmt = stmt.where(ReconciliationRecord.status == status)
    return list(db.execute(stmt).scalars().all())
