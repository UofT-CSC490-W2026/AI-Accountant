"""Pydantic models for SQS queue message validation.

Each model validates the fields that the SENDER provides at that pipeline stage.
ConfigDict(extra="allow") lets accumulated fields from previous stages pass through.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NormalizationTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    parse_id: str
    user_id: str
    source: str
    input_text: str | None = None
    currency: str | None = None
    filename: str | None = None
    submitted_at: str | None = None


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
    proposed_entry: dict | None = None
