from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from db.dao.journal_entries import JournalEntryDAO
from db.models.clarification import ClarificationTask
from db.models.journal import JournalEntry


def _normalize_entry_payload(payload: dict | None) -> tuple[dict, list[dict]]:
    if payload is None:
        raise ValueError("clarification resolution requires a proposed entry")
    if "entry" in payload and "lines" in payload:
        return dict(payload["entry"]), list(payload["lines"])
    entry = {key: value for key, value in payload.items() if key != "lines"}
    return entry, list(payload.get("lines", []))


def _json_safe_entry_payload(payload: dict) -> dict:
    normalized: dict = {}
    for key, value in payload.items():
        if isinstance(value, UUID):
            normalized[key] = str(value)
        else:
            normalized[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return normalized


class ClarificationDAO:
    @staticmethod
    def insert(
        db: Session,
        user_id,
        transaction_id,
        source_text: str,
        explanation: str,
        confidence,
        proposed_entry: dict | None,
        verdict: str,
    ) -> ClarificationTask:
        set_current_user_context(db, user_id)
        task = ClarificationTask(
            user_id=user_id,
            transaction_id=transaction_id,
            source_text=source_text,
            explanation=explanation,
            confidence=confidence,
            proposed_entry=proposed_entry,
            evaluator_verdict=verdict,
        )
        db.add(task)
        db.flush()
        return task

    @staticmethod
    def list_pending(db: Session, user_id) -> list[ClarificationTask]:
        set_current_user_context(db, user_id)
        stmt = (
            select(ClarificationTask)
            .where(
                ClarificationTask.user_id == user_id,
                ClarificationTask.status == "pending",
            )
            .order_by(ClarificationTask.created_at.asc())
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def resolve(
        db: Session,
        task_id,
        action: str,
        edited_entry: dict | None = None,
    ) -> tuple[ClarificationTask | None, JournalEntry | None]:
        task = db.get(ClarificationTask, task_id)
        if task is None:
            return None, None
        set_current_user_context(db, task.user_id)
        normalized_action = action.lower()
        now = datetime.now(timezone.utc)

        if normalized_action == "reject":
            task.status = "rejected"
            task.resolved_at = now
            db.flush()
            return task, None

        if normalized_action not in {"approve", "post", "resolve"}:
            raise ValueError(f"unsupported clarification action {action!r}")

        payload = edited_entry if edited_entry is not None else task.proposed_entry
        entry_payload, line_payload = _normalize_entry_payload(payload)
        entry_payload.setdefault("transaction_id", task.transaction_id)
        entry_payload.setdefault("status", "posted")

        journal_entry = JournalEntryDAO.insert_with_lines(db, task.user_id, entry_payload, line_payload)
        task.status = "resolved"
        task.resolved_at = now
        task.proposed_entry = {
            "entry": {
                **_json_safe_entry_payload(entry_payload),
                "journal_entry_id": str(journal_entry.id),
            },
            "lines": line_payload,
        }
        db.flush()
        return task, journal_entry

    @staticmethod
    def count_pending(db: Session, user_id) -> int:
        set_current_user_context(db, user_id)
        stmt = select(func.count()).select_from(ClarificationTask).where(
            ClarificationTask.user_id == user_id,
            ClarificationTask.status == "pending",
        )
        return int(db.execute(stmt).scalar_one())
