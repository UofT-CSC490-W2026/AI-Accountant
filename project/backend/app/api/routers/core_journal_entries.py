from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import JournalEntryDAO

router = APIRouter(prefix="/journal-entries", tags=["journal_entries"])


class JournalLineIn(BaseModel):
    account_code: str
    account_name: str | None = None
    type: str
    amount: float
    line_order: int | None = None


class JournalEntryCreateRequest(BaseModel):
    user_id: uuid.UUID
    transaction_id: uuid.UUID | None = None
    date: date
    description: str
    status: str = "draft"
    origin_tier: int | None = None
    confidence: float | None = None
    rationale: str | None = None
    posted_at: datetime | None = None
    lines: list[JournalLineIn]


class JournalLineResponse(BaseModel):
    id: uuid.UUID
    account_code: str
    account_name: str
    type: str
    amount: float
    line_order: int

    model_config = {"from_attributes": True}


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    transaction_id: uuid.UUID | None
    date: date
    description: str
    status: str
    origin_tier: int | None
    confidence: float | None
    rationale: str | None
    posted_at: datetime | None
    created_at: datetime
    lines: list[JournalLineResponse]

    model_config = {"from_attributes": True}


@router.post("/", response_model=JournalEntryResponse, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreateRequest, db: Session = Depends(get_db)
) -> JournalEntryResponse:
    entry = JournalEntryDAO.insert_with_lines(
        db,
        payload.user_id,
        payload.model_dump(exclude={"user_id", "lines"}),
        [line.model_dump(exclude_none=True) for line in payload.lines],
    )
    db.commit()
    db.refresh(entry)
    return JournalEntryResponse.model_validate(entry)


@router.get("/{journal_entry_id}", response_model=JournalEntryResponse)
def get_journal_entry(
    journal_entry_id: uuid.UUID, db: Session = Depends(get_db)
) -> JournalEntryResponse:
    entry = JournalEntryDAO.get_by_id(db, journal_entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    return JournalEntryResponse.model_validate(entry)


@router.get("/", response_model=list[JournalEntryResponse])
def list_journal_entries(
    user_id: uuid.UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    account: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[JournalEntryResponse]:
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "account": account,
        "status": status,
    }
    entries = JournalEntryDAO.list_by_user(db, user_id, filters)
    return [JournalEntryResponse.model_validate(entry) for entry in entries]
