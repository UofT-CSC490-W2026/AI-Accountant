"""Pydantic models for Redis pub/sub event validation."""

from __future__ import annotations

from pydantic import BaseModel


class EntryPostedEvent(BaseModel):
    type: str = "entry.posted"
    journal_entry_id: str
    parse_id: str
    user_id: str
    input_text: str | None = None
    occurred_at: str
    confidence: dict | None = None
    explanation: str | None = None
    status: str = "auto_posted"
    proposed_entry: dict | None = None
    parse_time_ms: int | None = None


class ClarificationCreatedEvent(BaseModel):
    type: str = "clarification.created"
    parse_id: str
    user_id: str
    input_text: str | None = None
    occurred_at: str
    confidence: dict | None = None
    explanation: str | None = None
    proposed_entry: dict | None = None


class ClarificationResolvedEvent(BaseModel):
    type: str = "clarification.resolved"
    parse_id: str
    user_id: str
    input_text: str | None = None
    occurred_at: str
    status: str
    confidence: dict | None = None
    explanation: str | None = None
    proposed_entry: dict | None = None
