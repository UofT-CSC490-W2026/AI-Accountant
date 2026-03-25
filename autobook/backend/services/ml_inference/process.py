from __future__ import annotations

import logging

from queues import sqs
from services.ml_inference.logic import get_inference_service

logger = logging.getLogger(__name__)


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    result = get_inference_service().enrich(message)
    sqs.enqueue.agent(result)
