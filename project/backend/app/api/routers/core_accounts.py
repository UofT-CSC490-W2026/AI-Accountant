from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import ChartOfAccountsDAO

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: str
    is_active: bool
    auto_created: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountCreateRequest(BaseModel):
    user_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: str


@router.get("/", response_model=list[AccountResponse])
def list_accounts(user_id: uuid.UUID = Query(...), db: Session = Depends(get_db)) -> list[AccountResponse]:
    return [AccountResponse.model_validate(a) for a in ChartOfAccountsDAO.list_by_user(db, user_id)]


@router.get("/by-code/{account_code}", response_model=AccountResponse)
def get_account_by_code(
    account_code: str,
    user_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
) -> AccountResponse:
    account = ChartOfAccountsDAO.get_by_code(db, user_id, account_code)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")
    return AccountResponse.model_validate(account)


@router.post("/get-or-create", response_model=AccountResponse, status_code=201)
def get_or_create_account(
    payload: AccountCreateRequest, db: Session = Depends(get_db)
) -> AccountResponse:
    account = ChartOfAccountsDAO.get_or_create(
        db,
        payload.user_id,
        payload.account_code,
        payload.account_name,
        payload.account_type,
    )
    db.commit()
    db.refresh(account)
    return AccountResponse.model_validate(account)


@router.post("/seed/{user_id}", response_model=list[AccountResponse], status_code=201)
def seed_accounts(user_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AccountResponse]:
    accounts = ChartOfAccountsDAO.seed_defaults(db, user_id)
    db.commit()
    return [AccountResponse.model_validate(a) for a in accounts]
