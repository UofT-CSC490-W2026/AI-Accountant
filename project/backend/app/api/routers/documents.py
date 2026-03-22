from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions.documents import DocumentDAO
from app.database import get_db
from app.models.enums import DocumentStatus, DocumentType

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Schemas ──────────────────────────────────────────────────────


class DocumentCreate(BaseModel):
    org_id: uuid.UUID
    document_type: DocumentType
    doc_date: date
    description: str | None = None
    generated_file_path: str | None = None
    related_journal_entry_id: uuid.UUID | None = None
    status: DocumentStatus = DocumentStatus.DRAFT


class DocumentOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    document_type: DocumentType
    date: date
    description: str | None
    generated_file_path: str | None
    related_journal_entry_id: uuid.UUID | None
    status: DocumentStatus

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/", response_model=DocumentOut, status_code=201)
def create(payload: DocumentCreate, db: Session = Depends(get_db)):
    dao = DocumentDAO(db)
    doc = dao.create(**payload.model_dump())
    db.commit()
    db.refresh(doc)
    return doc
