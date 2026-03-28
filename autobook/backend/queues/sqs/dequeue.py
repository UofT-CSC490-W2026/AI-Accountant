"""Typed dequeue functions — used by local __main__.py workers only.

In cloud, Lambda + SQS event source mapping replaces these.
"""

from __future__ import annotations

__all__ = ["normalization", "precedent", "ml_inference", "agent", "resolution", "posting", "flywheel"]

from config import get_settings
from queues.sqs.client import receive

settings = get_settings()


def normalization(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_NORMALIZER, wait_seconds)


def precedent(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_PRECEDENT, wait_seconds)


def ml_inference(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_ML_INFERENCE, wait_seconds)


def agent(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_AGENT, wait_seconds)


def resolution(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_RESOLUTION, wait_seconds)


def posting(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_POSTING, wait_seconds)


def flywheel(wait_seconds: int = 20) -> dict | None:
    return receive(settings.SQS_QUEUE_FLYWHEEL, wait_seconds)
