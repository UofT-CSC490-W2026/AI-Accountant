from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.shareholder_loans import ShareholderLoanDAO
from app.database import get_db

router = APIRouter(prefix="/shareholder-loans", tags=["shareholder_loans"])


# ── Schemas ──────────────────────────────────────────────────────


class LoanTransactionCreate(BaseModel):
    org_id: uuid.UUID
    shareholder_name: str
    transaction_date: date
    amount: Decimal
    description: str | None = None
    journal_entry_id: uuid.UUID | None = None


class LoanTransactionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    shareholder_name: str
    transaction_date: date
    amount: Decimal
    description: str | None
    journal_entry_id: uuid.UUID | None
    running_balance: Decimal

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    shareholder_name: str
    balance: Decimal


class Section152Check(BaseModel):
    org_id: uuid.UUID
    shareholder_name: str
    fiscal_year_end: date


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=LoanTransactionOut, status_code=201)
def create_transaction(payload: LoanTransactionCreate, db: Session = Depends(get_db)):
    dao = ShareholderLoanDAO(db)
    txn = dao.create_transaction(**payload.model_dump())
    db.commit()
    db.refresh(txn)
    return txn


@router.get("/org/{org_id}", response_model=list[LoanTransactionOut])
def list_transactions(
    org_id: uuid.UUID,
    shareholder_name: str | None = None,
    db: Session = Depends(get_db),
):
    dao = ShareholderLoanDAO(db)
    return dao.list_transactions(org_id=org_id, shareholder_name=shareholder_name)


@router.get("/balance/{org_id}/{shareholder_name}", response_model=BalanceOut)
def get_balance(
    org_id: uuid.UUID, shareholder_name: str, db: Session = Depends(get_db)
):
    dao = ShareholderLoanDAO(db)
    balance = dao.get_balance(org_id=org_id, shareholder_name=shareholder_name)
    return BalanceOut(shareholder_name=shareholder_name, balance=balance)


@router.post("/check-s152")
def check_s152(payload: Section152Check, db: Session = Depends(get_db)):
    dao = ShareholderLoanDAO(db)
    result = dao.check_section_15_2_warning(**payload.model_dump())
    return result or {"warning": None}
