from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_local_user
from db.connection import get_db
from reporting.statements import build_balance_sheet, build_income_statement, build_trial_balance
from schemas.statements import StatementResponse

router = APIRouter(prefix="/api/v1")


@router.get("/statements", response_model=StatementResponse)
async def get_statements(
    statement_type: str = Query(default="balance_sheet"),
    as_of: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_local_user),
):
    normalized_type = statement_type.lower()
    if normalized_type == "balance_sheet":
        payload = build_balance_sheet(db, current_user.id, as_of)
    elif normalized_type == "income_statement":
        payload = build_income_statement(db, current_user.id, as_of)
    elif normalized_type == "trial_balance":
        payload = build_trial_balance(db, current_user.id, as_of)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported statement_type {statement_type!r}",
        )

    return StatementResponse(**payload)
