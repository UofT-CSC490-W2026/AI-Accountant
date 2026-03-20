from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.accounts import (
    create_account,
    get_account,
    get_or_create_account,
    list_accounts,
    seed_chart_of_accounts,
)
from app.database import get_db
from app.models.enums import AccountCreator, AccountSubType, AccountType

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ── Schemas ──────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    org_id: uuid.UUID
    account_number: str
    name: str
    account_type: AccountType
    sub_type: AccountSubType | None = None
    parent_account_id: uuid.UUID | None = None
    currency: str = "CAD"
    is_active: bool = True
    created_by: AccountCreator = AccountCreator.USER
    auto_created: bool = False


class AccountOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    account_number: str
    name: str
    account_type: AccountType
    sub_type: AccountSubType | None
    parent_account_id: uuid.UUID | None
    currency: str
    is_active: bool
    created_by: AccountCreator
    auto_created: bool

    model_config = {"from_attributes": True}


class GetOrCreateRequest(BaseModel):
    org_id: uuid.UUID
    category: str
    currency: str = "CAD"


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=AccountOut, status_code=201)
def create_acct(payload: AccountCreate, db: Session = Depends(get_db)):
    account = create_account(db, **payload.model_dump())
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountOut)
def get_acct(account_id: uuid.UUID, db: Session = Depends(get_db)):
    return get_account(db, account_id)


@router.get("/org/{org_id}", response_model=list[AccountOut])
def list_accts(org_id: uuid.UUID, active_only: bool = True, db: Session = Depends(get_db)):
    return list_accounts(db, org_id=org_id, active_only=active_only)


@router.post("/get-or-create", response_model=AccountOut)
def get_or_create(payload: GetOrCreateRequest, db: Session = Depends(get_db)):
    account = get_or_create_account(db, **payload.model_dump())
    db.commit()
    db.refresh(account)
    return account


@router.post("/seed/{org_id}", response_model=list[AccountOut], status_code=201)
def seed_coa(org_id: uuid.UUID, db: Session = Depends(get_db)):
    accounts = seed_chart_of_accounts(db, org_id=org_id)
    db.commit()
    for a in accounts:
        db.refresh(a)
    return accounts
