import logging

from config import get_settings
from ml.service import enrich_message, get_inference_service
from queues import enqueue

logger = logging.getLogger(__name__)
settings = get_settings()


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # Keep the worker focused on orchestration; the inference implementation
    # lives in the ml service layer so it can be swapped independently later.
    result = get_inference_service().enrich(message)
    enqueue(settings.SQS_QUEUE_AGENT, result)
