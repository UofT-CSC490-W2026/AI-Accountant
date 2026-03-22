from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.document import CorporateDocument
from app.models.enums import DocumentStatus, DocumentType


class DocumentDAO:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        org_id: uuid.UUID,
        document_type: DocumentType,
        doc_date: date,
        description: str | None = None,
        generated_file_path: str | None = None,
        related_journal_entry_id: uuid.UUID | None = None,
        status: DocumentStatus = DocumentStatus.DRAFT,
    ) -> CorporateDocument:
        doc = CorporateDocument(
            org_id=org_id,
            document_type=document_type,
            date=doc_date,
            description=description,
            generated_file_path=generated_file_path,
            related_journal_entry_id=related_journal_entry_id,
            status=status,
        )
        self._db.add(doc)
        self._db.flush()
        return doc
