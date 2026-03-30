"""Data access for precedent_entries table.

Read-heavy: the matcher queries by vendor + time window.
Write: only the flywheel after human approval.
Invalidate: on CoA/tax structure changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from services.precedent_v2.models import PrecedentEntry, compute_structure_hash


class PrecedentDAO:
    @staticmethod
    def get_by_vendor(
        db: Session,
        user_id,
        vendor: str,
        time_window_days: int = 365,
    ) -> list[PrecedentEntry]:
        set_current_user_context(db, user_id)
        cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        stmt = (
            select(PrecedentEntry)
            .where(
                PrecedentEntry.user_id == user_id,
                PrecedentEntry.vendor == vendor,
                PrecedentEntry.created_at >= cutoff,
            )
            .order_by(PrecedentEntry.created_at.desc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def insert(
        db: Session,
        user_id,
        vendor: str,
        amount: Decimal,
        structure: dict,
        ratio: dict,
        source_journal_entry_id=None,
    ) -> PrecedentEntry:
        set_current_user_context(db, user_id)
        entry = PrecedentEntry(
            user_id=user_id,
            vendor=vendor,
            amount=amount,
            structure_hash=compute_structure_hash(structure),
            structure=structure,
            ratio=ratio,
            source_journal_entry_id=source_journal_entry_id,
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def invalidate_by_accounts(
        db: Session,
        user_id,
        account_codes: list[str],
    ) -> int:
        """Delete precedent entries whose structure references any of the given account codes."""
        set_current_user_context(db, user_id)
        entries = db.execute(
            select(PrecedentEntry).where(PrecedentEntry.user_id == user_id)
        ).scalars().all()

        deleted = 0
        for entry in entries:
            entry_codes = {line["account_code"] for line in entry.structure.get("lines", [])}
            if entry_codes & set(account_codes):
                db.delete(entry)
                deleted += 1
        db.flush()
        return deleted
