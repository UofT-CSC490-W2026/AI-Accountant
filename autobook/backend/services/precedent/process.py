import logging

from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
settings = get_settings()


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: match transaction against precedent patterns (tier 1)
    # On hit: enqueue to posting. On miss: enqueue to ml_inference.
    result = message  # stub: pass through
    enqueue(settings.SQS_QUEUE_ML_INFERENCE, result)
