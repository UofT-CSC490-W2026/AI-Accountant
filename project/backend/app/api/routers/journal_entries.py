from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.journal_entries import JournalEntryDAO
from app.database import get_db
from app.models.enums import JournalEntrySource, JournalEntryStatus

router = APIRouter(prefix="/journal-entries", tags=["journal_entries"])


# ── Schemas ──────────────────────────────────────────────────────


class JournalLineIn(BaseModel):
    account_id: uuid.UUID
    debit_amount: Decimal | None = None
    credit_amount: Decimal | None = None
    currency: str = "CAD"
    description: str | None = None
    line_order: int | None = None


class JournalEntryCreate(BaseModel):
    org_id: uuid.UUID
    entry_date: date
    description: str | None = None
    source: JournalEntrySource = JournalEntrySource.MANUAL
    source_reference_id: str | None = None
    status: JournalEntryStatus = JournalEntryStatus.DRAFT
    created_by: str | None = None
    lines: list[JournalLineIn]


class JournalLineOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    debit_amount: Decimal
    credit_amount: Decimal
    currency: str
    description: str | None
    line_order: int

    model_config = {"from_attributes": True}


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    entry_date: date
    posted_date: date | None
    description: str | None
    source: JournalEntrySource
    source_reference_id: str | None
    status: JournalEntryStatus
    created_by: str | None
    approved_by: str | None
    lines: list[JournalLineOut] = []

    model_config = {"from_attributes": True}


class PostRequest(BaseModel):
    approved_by: str | None = None
    posted_date: date | None = None


class ReverseRequest(BaseModel):
    reversal_date: date
    created_by: str | None = None
    approved_by: str | None = None


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=JournalEntryOut, status_code=201)
def create_entry(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    dao = JournalEntryDAO(db)
    data = payload.model_dump()
    data["lines"] = [line.model_dump() for line in payload.lines]
    entry = dao.create(**data)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=JournalEntryOut)
def get_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = JournalEntryDAO(db)
    return dao.get(entry_id)


@router.get("/org/{org_id}", response_model=list[JournalEntryOut])
def list_entries(
    org_id: uuid.UUID,
    status: JournalEntryStatus | None = None,
    db: Session = Depends(get_db),
):
    dao = JournalEntryDAO(db)
    return dao.list(org_id=org_id, status=status)


@router.post("/{entry_id}/post", response_model=JournalEntryOut)
def post_entry(
    entry_id: uuid.UUID,
    payload: PostRequest,
    db: Session = Depends(get_db),
):
    dao = JournalEntryDAO(db)
    entry = dao.post(journal_entry_id=entry_id, **payload.model_dump())
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/submit-for-review", response_model=JournalEntryOut)
def submit_review(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = JournalEntryDAO(db)
    entry = dao.submit_for_review(journal_entry_id=entry_id)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/reverse", response_model=JournalEntryOut)
def reverse_entry(
    entry_id: uuid.UUID,
    payload: ReverseRequest,
    db: Session = Depends(get_db),
):
    dao = JournalEntryDAO(db)
    reversal = dao.reverse(journal_entry_id=entry_id, **payload.model_dump())
    db.commit()
    db.refresh(reversal)
    return reversal
