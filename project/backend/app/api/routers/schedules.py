from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.schedules import ScheduleDAO
from app.database import get_db
from app.models.enums import ScheduleFrequency, ScheduleSource, ScheduleStatus

router = APIRouter(prefix="/schedules", tags=["schedules"])


# ── Schemas ──────────────────────────────────────────────────────


class ScheduleCreate(BaseModel):
    org_id: uuid.UUID
    template_journal_entry: dict
    frequency: ScheduleFrequency
    start_date: date
    end_date: date | None = None
    next_run_date: date
    source: ScheduleSource
    status: ScheduleStatus = ScheduleStatus.ACTIVE


class ScheduleOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    template_journal_entry: dict
    frequency: ScheduleFrequency
    start_date: date
    end_date: date | None
    next_run_date: date
    source: ScheduleSource
    status: ScheduleStatus

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=ScheduleOut, status_code=201)
def create(payload: ScheduleCreate, db: Session = Depends(get_db)):
    dao = ScheduleDAO(db)
    scheduled = dao.create(**payload.model_dump())
    db.commit()
    db.refresh(scheduled)
    return scheduled


@router.get("/org/{org_id}", response_model=list[ScheduleOut])
def list_all(
    org_id: uuid.UUID,
    status: ScheduleStatus | None = None,
    db: Session = Depends(get_db),
):
    dao = ScheduleDAO(db)
    return dao.list(org_id=org_id, status=status)


@router.post("/{entry_id}/pause", response_model=ScheduleOut)
def pause(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = ScheduleDAO(db)
    entry = dao.pause(scheduled_entry_id=entry_id)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/complete", response_model=ScheduleOut)
def complete(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    dao = ScheduleDAO(db)
    entry = dao.complete(scheduled_entry_id=entry_id)
    db.commit()
    db.refresh(entry)
    return entry
