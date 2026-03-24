"""Typed enqueue functions — one per pipeline stage.

Caller sees: sqs.enqueue.normalization(parse_id=..., input_text=..., ...)
Pydantic validates internally before sending to SQS.
"""

from __future__ import annotations

__all__ = ["normalization", "precedent", "ml_inference", "agent", "resolution", "posting", "flywheel"]

from config import get_settings
from queues.sqs.client import send
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
    input_text: str | None = None,
    currency: str | None = None,
    filename: str | None = None,
    submitted_at: str | None = None,
) -> str:
    msg = NormalizationTask(
        parse_id=parse_id,
        user_id=user_id,
        source=source,
        input_text=input_text,
        currency=currency,
        filename=filename,
        submitted_at=submitted_at,
    )
    return send(settings.SQS_QUEUE_NORMALIZER, msg.model_dump(exclude_none=True))


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
