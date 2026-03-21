from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import JournalEntryDAO

router = APIRouter(prefix="/ledger", tags=["ledger"])


class LedgerLineResponse(BaseModel):
    id: uuid.UUID
    account_code: str
    account_name: str
    type: str
    amount: Decimal
    line_order: int

    model_config = {"from_attributes": True}


class LedgerEntryResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID | None
    date: date
    description: str
    status: str
    origin_tier: int | None
    confidence: Decimal | None
    rationale: str | None
    posted_at: datetime | None
    lines: list[LedgerLineResponse]

    model_config = {"from_attributes": True}


class LedgerBalanceResponse(BaseModel):
    account_code: str
    account_name: str
    balance: Decimal


class LedgerSummaryResponse(BaseModel):
    total_debits: Decimal
    total_credits: Decimal


class LedgerResponse(BaseModel):
    entries: list[LedgerEntryResponse]
    balances: list[LedgerBalanceResponse]
    summary: LedgerSummaryResponse


@router.get("/", response_model=LedgerResponse)
def get_ledger(
    user_id: uuid.UUID = Query(...),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    account: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> LedgerResponse:
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "account": account,
        "status": status,
    }
    entries = JournalEntryDAO.list_by_user(db, user_id, filters)
    balances = JournalEntryDAO.compute_balances(db, user_id)
    summary = JournalEntryDAO.compute_summary(db, user_id)
    return LedgerResponse(
        entries=[LedgerEntryResponse.model_validate(entry) for entry in entries],
        balances=[LedgerBalanceResponse(**row) for row in balances],
        summary=LedgerSummaryResponse(**summary),
    )
