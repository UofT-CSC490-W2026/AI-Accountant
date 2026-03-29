from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.deps import AuthContext, get_current_user, require_role
from auth.schemas import UserRole
from config import get_settings
from db.connection import get_db
from db.dao.clarifications import ClarificationDAO
from db.models.clarification import ClarificationTask
from queues.pubsub import pub
publish_sync = pub.publish_sync
from schemas.clarifications import (
    ClarificationItem,
    ClarificationsResponse,
    ResolveRequest,
    ResolveResponse,
)
from schemas.parse import Confidence, JournalLine, ProposedEntry
from services.shared.parse_status import record_batch_result_sync

router = APIRouter(prefix="/api/v1")


def _normalize_entry_payload(payload: dict | None) -> tuple[dict, list[dict]]:
    if payload is None:
        return {}, []
    if "entry" in payload and "lines" in payload:
        return dict(payload.get("entry") or {}), list(payload.get("lines") or [])
    return ({key: value for key, value in payload.items() if key != "lines"}, list(payload.get("lines") or []))


def _serialize_line(line: dict) -> JournalLine:
    return JournalLine(
        account_code=str(line.get("account_code", "")),
        account_name=str(line.get("account_name", "")),
        type=str(line.get("type", "debit")),
        amount=float(line.get("amount", 0)),
    )


def _serialize_proposed_entry(task: ClarificationTask) -> ProposedEntry | None:
    if task.proposed_entry is None:
        return None

    entry_payload, line_payload = _normalize_entry_payload(task.proposed_entry)
    journal_entry_id = entry_payload.get("journal_entry_id") or entry_payload.get("id")
    if journal_entry_id is None and not line_payload:
        return None
    return ProposedEntry(
        journal_entry_id=str(journal_entry_id) if journal_entry_id is not None else None,
        lines=[_serialize_line(line) for line in line_payload],
    )


def _serialize_item(task: ClarificationTask) -> ClarificationItem:
    return ClarificationItem(
        clarification_id=str(task.id),
        status=task.status,
        source_text=task.source_text,
        explanation=task.explanation,
        confidence=Confidence(
            overall=float(task.confidence if isinstance(task.confidence, Decimal) else task.confidence),
            auto_post_threshold=get_settings().AUTO_POST_THRESHOLD,
        ),
        proposed_entry=_serialize_proposed_entry(task),
    )


def _normalize_resolve_payload(body: ResolveRequest) -> tuple[str, dict | None]:
    action = body.action.lower()
    if action == "edit":
        if body.edited_entry is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="edited_entry is required when action is 'edit'",
            )
        return "approve", body.edited_entry.model_dump(exclude_none=True)
    return action, body.edited_entry.model_dump(exclude_none=True) if body.edited_entry else None


@router.get("/clarifications", response_model=ClarificationsResponse)
async def get_clarifications(
    db: Session = Depends(get_db),
    current_user: AuthContext = Depends(get_current_user),
):
    items = ClarificationDAO.list_pending(db, current_user.user.id)
    serialized = [_serialize_item(item) for item in items]
    return ClarificationsResponse(items=serialized, count=len(serialized))


@router.post("/clarifications/{clarification_id}/resolve", response_model=ResolveResponse)
async def resolve_clarification(
    clarification_id: str,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    current_user: AuthContext = Depends(require_role(UserRole.MANAGER)),
):
    action, edited_entry = _normalize_resolve_payload(body)
    try:
        task_uuid = UUID(clarification_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clarification not found") from exc

    try:
        task, journal_entry = ClarificationDAO.resolve(db, task_uuid, action, edited_entry=edited_entry)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clarification not found")

    db.commit()

    stored_entry_payload, _ = _normalize_entry_payload(task.proposed_entry)
    event_parse_id = (
        stored_entry_payload.get("child_parse_id")
        or stored_entry_payload.get("parse_id")
        or clarification_id
    )

    pub.clarification_resolved(
        parse_id=str(event_parse_id),
        user_id=str(task.user_id),
        status=task.status,
        input_text=task.source_text,
        confidence={"overall": float(task.confidence)},
        explanation=task.explanation,
        proposed_entry=task.proposed_entry,
    )

    parent_parse_id = stored_entry_payload.get("parent_parse_id")
    child_parse_id = stored_entry_payload.get("child_parse_id") or stored_entry_payload.get("parse_id")
    if parent_parse_id and child_parse_id:
        record_batch_result_sync(
            parent_parse_id=str(parent_parse_id),
            child_parse_id=str(child_parse_id),
            user_id=str(task.user_id),
            statement_index=int(stored_entry_payload.get("statement_index") or 0),
            total_statements=int(stored_entry_payload.get("statement_total") or 1),
            status=task.status,
            input_text=task.source_text,
            journal_entry_id=str(journal_entry.id) if journal_entry is not None else None,
        )

    return ResolveResponse(
        clarification_id=clarification_id,
        status=task.status,
        journal_entry_id=str(journal_entry.id) if journal_entry is not None else None,
    )
