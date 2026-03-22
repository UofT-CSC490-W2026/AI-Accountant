from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.tax import TaxDAO
from app.database import get_db
from app.models.enums import TaxObligationStatus, TaxType

router = APIRouter(prefix="/tax", tags=["tax"])


# ── Schemas ──────────────────────────────────────────────────────


class TaxObligationCreate(BaseModel):
    org_id: uuid.UUID
    tax_type: TaxType
    period_start: date
    period_end: date
    amount_collected: Decimal = Decimal("0")
    itcs_claimed: Decimal = Decimal("0")
    net_owing: Decimal = Decimal("0")
    status: TaxObligationStatus = TaxObligationStatus.ACCRUING
    payment_journal_entry_id: uuid.UUID | None = None


class TaxObligationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    tax_type: TaxType
    period_start: date
    period_end: date
    amount_collected: Decimal
    itcs_claimed: Decimal
    net_owing: Decimal
    status: TaxObligationStatus
    payment_journal_entry_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class MarkPaidRequest(BaseModel):
    payment_journal_entry_id: uuid.UUID


class HSTSummaryRequest(BaseModel):
    org_id: uuid.UUID
    period_start: date
    period_end: date


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=TaxObligationOut, status_code=201)
def create(payload: TaxObligationCreate, db: Session = Depends(get_db)):
    dao = TaxDAO(db)
    obligation = dao.create(**payload.model_dump())
    db.commit()
    db.refresh(obligation)
    return obligation


@router.get("/{tax_id}", response_model=TaxObligationOut)
def get(tax_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = TaxDAO(db)
    return dao.get(tax_id)


@router.get("/org/{org_id}", response_model=list[TaxObligationOut])
def list_all(
    org_id: uuid.UUID,
    tax_type: TaxType | None = None,
    status: TaxObligationStatus | None = None,
    db: Session = Depends(get_db),
):
    dao = TaxDAO(db)
    return dao.list(org_id=org_id, tax_type=tax_type, status=status)


@router.post("/{tax_id}/filed", response_model=TaxObligationOut)
def mark_filed(tax_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = TaxDAO(db)
    obligation = dao.mark_filed(tax_obligation_id=tax_id)
    db.commit()
    db.refresh(obligation)
    return obligation


@router.post("/{tax_id}/paid", response_model=TaxObligationOut)
def mark_paid(
    tax_id: uuid.UUID,
    payload: MarkPaidRequest,
    db: Session = Depends(get_db),
):
    dao = TaxDAO(db)
    obligation = dao.mark_paid(tax_obligation_id=tax_id, **payload.model_dump())
    db.commit()
    db.refresh(obligation)
    return obligation


@router.post("/hst-summary")
def hst_summary(payload: HSTSummaryRequest, db: Session = Depends(get_db)):
    dao = TaxDAO(db)
    return dao.calculate_hst_net_owing(**payload.model_dump())
