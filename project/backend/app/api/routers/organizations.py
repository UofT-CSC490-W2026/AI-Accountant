from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.organizations import OrganizationDAO
from app.database import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


# ── Schemas ──────────────────────────────────────────────────────


class OrganizationCreate(BaseModel):
    name: str
    fiscal_year_end: date
    jurisdiction: str
    incorporation_date: date | None = None
    hst_registration_number: str | None = None
    business_number: str | None = None


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    fiscal_year_end: date
    jurisdiction: str
    incorporation_date: date | None
    hst_registration_number: str | None
    business_number: str | None

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=OrganizationOut, status_code=201)
def create_org(payload: OrganizationCreate, db: Session = Depends(get_db)):
    dao = OrganizationDAO(db)
    org = dao.create(**payload.model_dump())
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_org(org_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = OrganizationDAO(db)
    return dao.get(org_id)
