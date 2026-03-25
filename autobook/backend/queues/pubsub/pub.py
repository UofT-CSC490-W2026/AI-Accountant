"""Typed publish functions — one per event type.

Caller sees: pubsub.pub.entry_posted(journal_entry_id=..., ...)
Pydantic validates before publishing to Redis.
"""

from __future__ import annotations

from datetime import datetime, timezone

from queues.pubsub.client import publish_sync
from schemas.events import (
    ClarificationCreatedEvent,
    ClarificationResolvedEvent,
    EntryPostedEvent,
    PipelineErrorEvent,
    PipelineResultEvent,
)

__all__ = ["entry_posted", "clarification_created", "clarification_resolved", "pipeline_result", "pipeline_error"]


def entry_posted(
    *,
    journal_entry_id: str,
    parse_id: str,
    user_id: str,
    input_text: str | None = None,
    confidence: dict | None = None,
    explanation: str | None = None,
    status: str = "auto_posted",
    proposed_entry: dict | None = None,
    parse_time_ms: int | None = None,
) -> None:
    event = EntryPostedEvent(
        journal_entry_id=journal_entry_id,
        parse_id=parse_id,
        user_id=user_id,
        input_text=input_text,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        confidence=confidence,
        explanation=explanation,
        status=status,
        proposed_entry=proposed_entry,
        parse_time_ms=parse_time_ms,
    )
    publish_sync("entry.posted", event.model_dump())


def clarification_created(
    *,
    parse_id: str,
    user_id: str,
    input_text: str | None = None,
    confidence: dict | None = None,
    explanation: str | None = None,
    proposed_entry: dict | None = None,
) -> None:
    event = ClarificationCreatedEvent(
        parse_id=parse_id,
        user_id=user_id,
        input_text=input_text,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        confidence=confidence,
        explanation=explanation,
        proposed_entry=proposed_entry,
    )
    publish_sync("clarification.created", event.model_dump())


def clarification_resolved(
    *,
    parse_id: str,
    user_id: str,
    status: str,
    input_text: str | None = None,
    confidence: dict | None = None,
    explanation: str | None = None,
    proposed_entry: dict | None = None,
) -> None:
    event = ClarificationResolvedEvent(
        parse_id=parse_id,
        user_id=user_id,
        status=status,
        input_text=input_text,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        confidence=confidence,
        explanation=explanation,
        proposed_entry=proposed_entry,
    )
    publish_sync("clarification.resolved", event.model_dump())


def pipeline_result(
    *,
    parse_id: str,
    user_id: str,
    stage: str,
    result: dict,
) -> None:
    event = PipelineResultEvent(
        parse_id=parse_id,
        user_id=user_id,
        stage=stage,
        result=result,
        occurred_at=datetime.now(timezone.utc).isoformat(),
    )
    publish_sync("pipeline.result", event.model_dump())


def pipeline_error(
    *,
    parse_id: str,
    user_id: str,
    stage: str,
    error: str,
) -> None:
    event = PipelineErrorEvent(
        parse_id=parse_id,
        user_id=user_id,
        stage=stage,
        error=error,
        occurred_at=datetime.now(timezone.utc).isoformat(),
    )
    publish_sync("pipeline.error", event.model_dump())
