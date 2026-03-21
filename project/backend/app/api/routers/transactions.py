from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import TransactionDAO

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionCreateRequest(BaseModel):
    user_id: uuid.UUID
    description: str
    amount: float
    currency: str = "CAD"
    date: date
    source: str
    counterparty: str | None = None


class TransactionEnrichmentRequest(BaseModel):
    intent_label: str | None = None
    entities: dict | None = None
    bank_category: str | None = None
    cca_class_match: str | None = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    description: str
    normalized_description: str | None
    amount: float
    currency: str
    date: date
    source: str
    counterparty: str | None
    intent_label: str | None
    entities: dict | None
    bank_category: str | None
    cca_class_match: str | None
    submitted_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=TransactionResponse, status_code=201)
def create_transaction(
    payload: TransactionCreateRequest, db: Session = Depends(get_db)
) -> TransactionResponse:
    transaction = TransactionDAO.insert(
        db,
        payload.user_id,
        payload.description,
        payload.amount,
        payload.currency,
        payload.date,
        payload.source,
        payload.counterparty,
    )
    db.commit()
    db.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.patch("/{transaction_id}/ml-enrichment", response_model=TransactionResponse)
def update_ml_enrichment(
    transaction_id: uuid.UUID,
    payload: TransactionEnrichmentRequest,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    transaction = TransactionDAO.update_ml_enrichment(
        db,
        transaction_id,
        payload.intent_label,
        payload.entities,
        payload.bank_category,
        payload.cca_class_match,
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    db.commit()
    db.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: uuid.UUID, db: Session = Depends(get_db)) -> TransactionResponse:
    transaction = TransactionDAO.get_by_id(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return TransactionResponse.model_validate(transaction)
