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


def _resolve_posting_payload(task: ClarificationTask, edited_entry: dict | None) -> tuple[dict, list[dict]]:
    if edited_entry is None:
        return _normalize_entry_payload(task.proposed_entry)

    edited_entry_payload, edited_line_payload = _normalize_entry_payload(edited_entry)
    if task.proposed_entry is None:
        return edited_entry_payload, edited_line_payload

    base_entry_payload, _ = _normalize_entry_payload(task.proposed_entry)
    return {**base_entry_payload, **edited_entry_payload}, edited_line_payload


def _apply_entry_defaults(task: ClarificationTask, entry_payload: dict) -> dict:
    normalized_payload = dict(entry_payload)

    if "date" not in normalized_payload:
        transaction_date = getattr(getattr(task, "transaction", None), "date", None)
        if transaction_date is not None:
            normalized_payload["date"] = transaction_date

    if "description" not in normalized_payload:
        transaction_description = getattr(getattr(task, "transaction", None), "description", None)
        normalized_payload["description"] = transaction_description or task.source_text

    if "rationale" not in normalized_payload:
        normalized_payload["rationale"] = task.explanation

    if "origin_tier" not in normalized_payload:
        normalized_payload["origin_tier"] = 3

    return normalized_payload


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

        entry_payload, line_payload = _resolve_posting_payload(task, edited_entry)
        entry_payload = _apply_entry_defaults(task, entry_payload)
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
