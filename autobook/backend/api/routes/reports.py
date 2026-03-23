from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.connection import get_db
from services.actions.reports import balance_sheet, income_statement, trial_balance

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/trial-balance")
def get_trial_balance(
    user_id: uuid.UUID,
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    return trial_balance(db, user_id=user_id, as_of=as_of)


@router.get("/balance-sheet")
def get_balance_sheet(
    user_id: uuid.UUID,
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    return balance_sheet(db, user_id=user_id, as_of=as_of)


@router.get("/income-statement")
def get_income_statement(
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    return income_statement(
        db, user_id=user_id, start_date=start_date, end_date=end_date
    )
