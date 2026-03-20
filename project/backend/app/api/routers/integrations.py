from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.integrations import (
    create_integration_connection,
    list_integration_connections,
    update_integration_status,
)
from app.database import get_db
from app.models.enums import IntegrationPlatform, IntegrationStatus

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ── Schemas ──────────────────────────────────────────────────────


class IntegrationCreate(BaseModel):
    org_id: uuid.UUID
    platform: IntegrationPlatform
    credentials: str | None = None
    status: IntegrationStatus = IntegrationStatus.INACTIVE
    last_sync: datetime | None = None
    webhook_secret: str | None = None
    config: dict | None = None


class IntegrationOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    platform: IntegrationPlatform
    status: IntegrationStatus
    last_sync: datetime | None
    config: dict | None

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: IntegrationStatus
    last_sync: datetime | None = None


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=IntegrationOut, status_code=201)
def create(payload: IntegrationCreate, db: Session = Depends(get_db)):
    conn = create_integration_connection(db, **payload.model_dump())
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/org/{org_id}", response_model=list[IntegrationOut])
def list_all(org_id: uuid.UUID, db: Session = Depends(get_db)):
    return list_integration_connections(db, org_id=org_id)


@router.post("/{conn_id}/status", response_model=IntegrationOut)
def update_status(
    conn_id: uuid.UUID,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    conn = update_integration_status(
        db, connection_id=conn_id, **payload.model_dump()
    )
    db.commit()
    db.refresh(conn)
    return conn
