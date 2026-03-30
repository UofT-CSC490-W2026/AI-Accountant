"""Typed enqueue functions — one per pipeline stage.

Caller sees: sqs.enqueue.normalization(parse_id=..., input_text=..., ...)
Pydantic validates internally before sending to SQS.
"""

from __future__ import annotations

__all__ = ["normalization", "precedent", "ml_inference", "agent", "resolution", "posting", "flywheel"]

from config import get_settings
from queues.sqs.client import send
from schemas.parse import DEFAULT_POST_STAGES, DEFAULT_STAGES
from schemas.queue_messages import (
    AgentTask,
    FlywheelTask,
    MLInferenceTask,
    NormalizationTask,
    PostingTask,
    PrecedentTask,
    ResolutionTask,
)

settings = get_settings()


def normalization(
    *,
    parse_id: str,
    user_id: str,
    source: str,
    parent_parse_id: str | None = None,
    statement_index: int | None = None,
    statement_total: int | None = None,
    input_text: str | None = None,
    currency: str | None = None,
    filename: str | None = None,
    transaction_date: str | None = None,
    amount: float | None = None,
    counterparty: str | None = None,
    submitted_at: str | None = None,
    stages: list[str] | None = None,
    store: bool = True,
    post_stages: list[str] | None = None,
) -> str:
    msg = NormalizationTask(
        parse_id=parse_id,
        user_id=user_id,
        source=source,
        parent_parse_id=parent_parse_id,
        statement_index=statement_index,
        statement_total=statement_total,
        input_text=input_text,
        currency=currency,
        filename=filename,
        transaction_date=transaction_date,
        amount=amount,
        counterparty=counterparty,
        submitted_at=submitted_at,
        stages=stages if stages is not None else list(DEFAULT_STAGES),
        store=store,
        post_stages=post_stages if post_stages is not None else list(DEFAULT_POST_STAGES),
    )
    return send(settings.SQS_QUEUE_NORMALIZER, msg.model_dump(exclude_none=True))


def by_name(stage: str, message: dict) -> str:
    """Enqueue a message to the queue for the given stage name."""
    from services.shared.routing import queue_url_for_stage

    url = queue_url_for_stage(stage)
    return send(url, message)


def precedent(message: dict) -> str:
    PrecedentTask.model_validate(message)
    return send(settings.SQS_QUEUE_PRECEDENT, message)


def ml_inference(message: dict) -> str:
    MLInferenceTask.model_validate(message)
    return send(settings.SQS_QUEUE_ML_INFERENCE, message)


def agent(message: dict) -> str:
    AgentTask.model_validate(message)
    return send(settings.SQS_QUEUE_AGENT, message)


def resolution(message: dict) -> str:
    ResolutionTask.model_validate(message)
    return send(settings.SQS_QUEUE_RESOLUTION, message)


def posting(message: dict) -> str:
    PostingTask.model_validate(message)
    return send(settings.SQS_QUEUE_POSTING, message)


def flywheel(message: dict) -> str:
    FlywheelTask.model_validate(message)
    return send(settings.SQS_QUEUE_FLYWHEEL, message)
