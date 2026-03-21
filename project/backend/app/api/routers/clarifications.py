from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import ClarificationDAO

router = APIRouter(prefix="/clarifications", tags=["clarifications"])


class ClarificationCreateRequest(BaseModel):
    user_id: uuid.UUID
    transaction_id: uuid.UUID
    source_text: str
    explanation: str
    confidence: Decimal
    proposed_entry: dict | None = None
    verdict: str


class ClarificationResolveRequest(BaseModel):
    action: str
    edited_entry: dict | None = None


class ClarificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    transaction_id: uuid.UUID
    status: str
    source_text: str
    explanation: str
    confidence: Decimal
    proposed_entry: dict | None
    evaluator_verdict: str
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClarificationCountResponse(BaseModel):
    pending: int


@router.post("/", response_model=ClarificationResponse, status_code=201)
def create_clarification(
    payload: ClarificationCreateRequest, db: Session = Depends(get_db)
) -> ClarificationResponse:
    task = ClarificationDAO.insert(
        db,
        payload.user_id,
        payload.transaction_id,
        payload.source_text,
        payload.explanation,
        payload.confidence,
        payload.proposed_entry,
        payload.verdict,
    )
    db.commit()
    db.refresh(task)
    return ClarificationResponse.model_validate(task)


@router.get("/pending", response_model=list[ClarificationResponse])
def list_pending_clarifications(
    user_id: uuid.UUID = Query(...), db: Session = Depends(get_db)
) -> list[ClarificationResponse]:
    tasks = ClarificationDAO.list_pending(db, user_id)
    return [ClarificationResponse.model_validate(task) for task in tasks]


@router.get("/count", response_model=ClarificationCountResponse)
def count_pending_clarifications(
    user_id: uuid.UUID = Query(...), db: Session = Depends(get_db)
) -> ClarificationCountResponse:
    return ClarificationCountResponse(pending=ClarificationDAO.count_pending(db, user_id))


@router.post("/{task_id}/resolve", response_model=ClarificationResponse)
def resolve_clarification(
    task_id: uuid.UUID,
    payload: ClarificationResolveRequest,
    db: Session = Depends(get_db),
) -> ClarificationResponse:
    task = ClarificationDAO.resolve(db, task_id, payload.action, payload.edited_entry)
    if task is None:
        raise HTTPException(status_code=404, detail="clarification task not found")
    db.commit()
    db.refresh(task)
    return ClarificationResponse.model_validate(task)
