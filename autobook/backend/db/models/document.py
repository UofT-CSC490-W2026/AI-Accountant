from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models.base import AuditMixin, Base
from db.models.enums import DocumentStatus, DocumentType

if TYPE_CHECKING:
    from db.models.journal import JournalEntry
    from db.models.organization import Organization


class CorporateDocument(AuditMixin, Base):
    __tablename__ = "corporate_documents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    document_type: Mapped[DocumentType]
    date: Mapped[date]
    description: Mapped[str | None] = mapped_column(Text)
    generated_file_path: Mapped[str | None] = mapped_column(String(500))
    related_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("journal_entries.id")
    )
    status: Mapped[DocumentStatus] = mapped_column(default=DocumentStatus.DRAFT)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="corporate_documents"
    )
    related_journal_entry: Mapped["JournalEntry | None"] = relationship(
        "JournalEntry"
    )
