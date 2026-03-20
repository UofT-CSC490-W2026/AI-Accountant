from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base
from app.models.enums import ScheduleFrequency, ScheduleSource, ScheduleStatus

if TYPE_CHECKING:
    from app.models.organization import Organization


class ScheduledEntry(AuditMixin, Base):
    __tablename__ = "scheduled_entries"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    template_journal_entry: Mapped[dict] = mapped_column(JSONB)
    frequency: Mapped[ScheduleFrequency]
    start_date: Mapped[date]
    end_date: Mapped[date | None]
    next_run_date: Mapped[date]
    source: Mapped[ScheduleSource]
    status: Mapped[ScheduleStatus] = mapped_column(default=ScheduleStatus.ACTIVE)

    # ── relationships ──────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="scheduled_entries"
    )
