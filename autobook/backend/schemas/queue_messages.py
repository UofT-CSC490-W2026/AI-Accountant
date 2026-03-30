"""Pydantic models for SQS queue message validation.

Each model validates the fields that the SENDER provides at that pipeline stage.
ConfigDict(extra="allow") lets accumulated fields from previous stages pass through.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from schemas.parse import DEFAULT_POST_STAGES, DEFAULT_STAGES


class NormalizationTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    source: str
    parent_parse_id: str | None = None
    statement_index: int | None = None
    statement_total: int | None = None
    input_text: str | None = None
    currency: str | None = None
    filename: str | None = None
    transaction_date: str | None = None
    amount: float | None = None
    counterparty: str | None = None
    submitted_at: str | None = None
    stages: list[str] = Field(default_factory=lambda: list(DEFAULT_STAGES))
    store: bool = True
    post_stages: list[str] = Field(default_factory=lambda: list(DEFAULT_POST_STAGES))


class PrecedentTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    transaction_id: str
    normalized_description: str


class MLInferenceTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    transaction_id: str
    precedent_match: dict


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    intent_label: str | None = None
    entities: dict | None = None
    bank_category: str | None = None
    cca_class_match: str | None = None
    confidence: dict | None = None


class ResolutionTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    confidence: dict
    explanation: str
    proposed_entry: dict | None = None
    clarification: dict


class PostingTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    confidence: dict
    proposed_entry: dict | None = None


class FlywheelTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    transaction_id: str
    journal_entry_id: str
    origin_tier: int | None = None
    proposed_entry: dict | None = None
