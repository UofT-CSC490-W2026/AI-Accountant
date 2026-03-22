from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_local_user
from config import get_settings
from db.connection import get_db
from db.dao.clarifications import ClarificationDAO
from db.models.clarification import ClarificationTask
from queues.redis import publish_sync
from schemas.clarifications import (
    ClarificationItem,
    ClarificationsResponse,
    ResolveRequest,
    ResolveResponse,
)
from schemas.parse import Confidence, JournalLine, ProposedEntry

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


def _serialize_proposed_entry(task: ClarificationTask) -> ProposedEntry:
    entry_payload, line_payload = _normalize_entry_payload(task.proposed_entry)
    journal_entry_id = entry_payload.get("journal_entry_id") or entry_payload.get("id")
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
    current_user=Depends(get_current_local_user),
):
    items = ClarificationDAO.list_pending(db, current_user.id)
    serialized = [_serialize_item(item) for item in items]
    return ClarificationsResponse(items=serialized, count=len(serialized))


@router.post("/clarifications/{clarification_id}/resolve", response_model=ResolveResponse)
async def resolve_clarification(
    clarification_id: str,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_local_user),
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
    if task.user_id != current_user.id:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clarification not found")

    db.commit()

    publish_sync(
        "clarification.resolved",
        {
            "type": "clarification.resolved",
            "clarification_id": clarification_id,
            "user_id": str(current_user.id),
            "input_text": task.source_text,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "status": task.status,
            "confidence": {"overall": float(task.confidence)},
            "explanation": task.explanation,
            "proposed_entry": task.proposed_entry,
        },
    )

    return ResolveResponse(
        clarification_id=clarification_id,
        status=task.status,
        journal_entry_id=str(journal_entry.id) if journal_entry is not None else None,
    )
