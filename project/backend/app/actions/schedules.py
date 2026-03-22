from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError
from app.models.enums import ScheduleFrequency, ScheduleSource, ScheduleStatus
from app.models.schedule import ScheduledEntry


class ScheduleDAO:
    def __init__(self, db: Session):
        self._db = db

    def create(
        self,
        *,
        org_id: uuid.UUID,
        template_journal_entry: dict,
        frequency: ScheduleFrequency,
        start_date: date,
        end_date: date | None = None,
        next_run_date: date,
        source: ScheduleSource,
        status: ScheduleStatus = ScheduleStatus.ACTIVE,
    ) -> ScheduledEntry:
        scheduled = ScheduledEntry(
            org_id=org_id,
            template_journal_entry=template_journal_entry,
            frequency=frequency,
            start_date=start_date,
            end_date=end_date,
            next_run_date=next_run_date,
            source=source,
            status=status,
        )
        self._db.add(scheduled)
        self._db.flush()
        return scheduled

    def pause(self, *, scheduled_entry_id: uuid.UUID) -> ScheduledEntry:
        entry = self._db.get(ScheduledEntry, scheduled_entry_id)
        if entry is None:
            raise NotFoundError(f"scheduled entry {scheduled_entry_id} not found")
        entry.status = ScheduleStatus.PAUSED
        self._db.flush()
        return entry

    def complete(self, *, scheduled_entry_id: uuid.UUID) -> ScheduledEntry:
        entry = self._db.get(ScheduledEntry, scheduled_entry_id)
        if entry is None:
            raise NotFoundError(f"scheduled entry {scheduled_entry_id} not found")
        entry.status = ScheduleStatus.COMPLETED
        self._db.flush()
        return entry

    def list(
        self,
        *,
        org_id: uuid.UUID,
        status: ScheduleStatus | None = None,
    ) -> list[ScheduledEntry]:
        stmt = select(ScheduledEntry).where(ScheduledEntry.org_id == org_id)
        if status is not None:
            stmt = stmt.where(ScheduledEntry.status == status)
        stmt = stmt.order_by(ScheduledEntry.next_run_date)
        return list(self._db.execute(stmt).scalars().all())
