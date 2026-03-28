"""Shared pipeline routing logic.

Each message carries `stages` (list of stage names to run) and `post_stages`
(list of stages that should auto-post when confident). This module provides
helpers that aws.py handlers call after execute() to decide the next hop.
"""

from __future__ import annotations

from config import get_settings

PIPELINE_ORDER = ["precedent", "ml", "llm"]

STAGE_TO_QUEUE_ATTR = {
    "precedent": "SQS_QUEUE_PRECEDENT",
    "ml": "SQS_QUEUE_ML_INFERENCE",
    "llm": "SQS_QUEUE_AGENT",
}


def next_stage(current: str, message: dict) -> str | None:
    """Return the next stage name in the pipeline that the message should visit, or None."""
    stages = message.get("stages", PIPELINE_ORDER)
    try:
        idx = PIPELINE_ORDER.index(current)
    except ValueError:
        return None
    for s in PIPELINE_ORDER[idx + 1:]:
        if s in stages:
            return s
    return None


def should_post(current: str, message: dict) -> bool:
    """Return True if this stage should send the message to posting."""
    post_stages = message.get("post_stages", [])
    store = message.get("store", True)
    if not store:
        return False
    confidence = (message.get("confidence") or {}).get("overall", 0)
    settings = get_settings()
    return current in post_stages and confidence >= settings.AUTO_POST_THRESHOLD


def queue_url_for_stage(stage: str) -> str:
    """Return the SQS queue URL for a given stage name."""
    settings = get_settings()
    attr = STAGE_TO_QUEUE_ATTR.get(stage)
    if not attr:
        raise ValueError(f"Unknown stage: {stage}")
    return getattr(settings, attr)


def first_stage(message: dict) -> str | None:
    """Return the first stage the message should visit after normalizer."""
    stages = message.get("stages", PIPELINE_ORDER)
    for s in PIPELINE_ORDER:
        if s in stages:
            return s
    return None
