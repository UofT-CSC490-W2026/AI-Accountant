from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.reconciliation import (
    confirm_reconciliation,
    create_reconciliation_record,
    list_reconciliation_records,
)
from app.database import get_db
from app.models.enums import ReconciliationStatus

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


# ── Schemas ──────────────────────────────────────────────────────


class ReconciliationCreate(BaseModel):
    org_id: uuid.UUID
    bank_transaction_id: str | None = None
    platform_transaction_ids: list[str] | None = None
    status: ReconciliationStatus
    matched_amount: Decimal | None = None
    discrepancy_amount: Decimal | None = None
    journal_entry_id: uuid.UUID | None = None


class ReconciliationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    bank_transaction_id: str | None
    platform_transaction_ids: list[str] | None
    status: ReconciliationStatus
    matched_amount: Decimal | None
    discrepancy_amount: Decimal | None
    journal_entry_id: uuid.UUID | None

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=ReconciliationOut, status_code=201)
def create(payload: ReconciliationCreate, db: Session = Depends(get_db)):
    rec = create_reconciliation_record(db, **payload.model_dump())
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/org/{org_id}", response_model=list[ReconciliationOut])
def list_all(
    org_id: uuid.UUID,
    status: ReconciliationStatus | None = None,
    db: Session = Depends(get_db),
):
    return list_reconciliation_records(db, org_id=org_id, status=status)


@router.post("/{record_id}/confirm", response_model=ReconciliationOut)
def confirm(record_id: uuid.UUID, db: Session = Depends(get_db)):
    rec = confirm_reconciliation(db, record_id=record_id)
    db.commit()
    db.refresh(rec)
    return rec
