from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.assets import AssetDAO
from app.database import get_db
from app.models.enums import AssetStatus

router = APIRouter(prefix="/assets", tags=["assets"])


# ── Schemas ──────────────────────────────────────────────────────


class AssetCreate(BaseModel):
    org_id: uuid.UUID
    name: str
    acquisition_date: date
    acquisition_cost: Decimal
    description: str | None = None
    cca_class: str | None = None
    cca_rate: Decimal | None = None
    book_depreciation_method: str | None = None
    book_useful_life: int | None = None


class AssetOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    acquisition_date: date
    acquisition_cost: Decimal
    cca_class: str | None
    cca_rate: Decimal | None
    disposition_date: date | None
    disposition_proceeds: Decimal | None
    status: AssetStatus

    model_config = {"from_attributes": True}


class DisposeRequest(BaseModel):
    disposition_date: date
    disposition_proceeds: Decimal


class CCACalcRequest(BaseModel):
    fiscal_year: int
    journal_entry_id: uuid.UUID | None = None


class CCAScheduleEntryCreate(BaseModel):
    asset_id: uuid.UUID
    fiscal_year: int
    ucc_opening: Decimal
    additions: Decimal
    dispositions: Decimal
    cca_claimed: Decimal
    ucc_closing: Decimal
    half_year_rule_applied: bool = False
    aiip_applied: bool = False
    journal_entry_id: uuid.UUID | None = None


class CCAScheduleEntryOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    fiscal_year: int
    ucc_opening: Decimal
    additions: Decimal
    dispositions: Decimal
    cca_claimed: Decimal
    ucc_closing: Decimal
    half_year_rule_applied: bool
    aiip_applied: bool
    journal_entry_id: uuid.UUID | None

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=AssetOut, status_code=201)
def create(payload: AssetCreate, db: Session = Depends(get_db)):
    dao = AssetDAO(db)
    asset = dao.create(**payload.model_dump())
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=AssetOut)
def get(asset_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = AssetDAO(db)
    return dao.get(asset_id)


@router.get("/org/{org_id}", response_model=list[AssetOut])
def list_all(
    org_id: uuid.UUID,
    status: AssetStatus | None = None,
    db: Session = Depends(get_db),
):
    dao = AssetDAO(db)
    return dao.list(org_id=org_id, status=status)


@router.post("/{asset_id}/dispose", response_model=AssetOut)
def dispose(
    asset_id: uuid.UUID, payload: DisposeRequest, db: Session = Depends(get_db)
):
    dao = AssetDAO(db)
    asset = dao.dispose(asset_id=asset_id, **payload.model_dump())
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/{asset_id}/calculate-cca", response_model=CCAScheduleEntryOut)
def calc_cca(
    asset_id: uuid.UUID, payload: CCACalcRequest, db: Session = Depends(get_db)
):
    dao = AssetDAO(db)
    entry = dao.calculate_annual_cca(asset_id=asset_id, **payload.model_dump())
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/cca-schedule", response_model=CCAScheduleEntryOut, status_code=201)
def create_cca(payload: CCAScheduleEntryCreate, db: Session = Depends(get_db)):
    dao = AssetDAO(db)
    entry = dao.create_cca_schedule_entry(**payload.model_dump())
    db.commit()
    db.refresh(entry)
    return entry
