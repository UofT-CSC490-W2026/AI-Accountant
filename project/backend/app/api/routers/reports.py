from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.actions.reports import balance_sheet, income_statement, trial_balance
from app.database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/trial-balance/{org_id}")
def get_trial_balance(
    org_id: uuid.UUID,
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    return trial_balance(db, org_id=org_id, as_of=as_of)


@router.get("/balance-sheet/{org_id}")
def get_balance_sheet(
    org_id: uuid.UUID,
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    return balance_sheet(db, org_id=org_id, as_of=as_of)


@router.get("/income-statement/{org_id}")
def get_income_statement(
    org_id: uuid.UUID,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    return income_statement(
        db, org_id=org_id, start_date=start_date, end_date=end_date
    )
