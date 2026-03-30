"""PrecedentEntry model — stores human-reviewed journal entry patterns.

Only the flywheel writes to this table. The precedent matcher only reads.
Bypassed entries are never written here.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.models.base import Base


class PrecedentEntry(Base):
    __tablename__ = "precedent_entries"
    __table_args__ = (
        Index("ix_precedent_user_vendor_created", "user_id", "vendor", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    vendor: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    structure_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    structure: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ratio: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Value objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StructureLine:
    account_code: str
    side: str  # "debit" or "credit"


@dataclass(frozen=True)
class RatioLine:
    account_code: str
    ratio: float


@dataclass(frozen=True)
class Label:
    """The (structure, ratio) pair that identifies an equivalence class."""
    structure: tuple[StructureLine, ...]
    ratio: tuple[RatioLine, ...]
    structure_hash: str


def compute_structure_hash(structure: dict) -> str:
    """Deterministic hash of structure for fast equality checks."""
    canonical = json.dumps(structure, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def extract_label(entry: PrecedentEntry) -> Label:
    """Extract the (structure, ratio) label from a precedent entry."""
    structure_lines = tuple(
        StructureLine(account_code=line["account_code"], side=line["side"])
        for line in entry.structure.get("lines", [])
    )
    ratio_lines = tuple(
        RatioLine(account_code=line["account_code"], ratio=line["ratio"])
        for line in entry.ratio.get("lines", [])
    )
    return Label(
        structure=structure_lines,
        ratio=ratio_lines,
        structure_hash=entry.structure_hash,
    )
