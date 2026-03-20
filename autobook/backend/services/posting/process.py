import logging

from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
settings = get_settings()


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: write journal entry to database
    result = message  # stub: pass through
    enqueue(settings.SQS_QUEUE_FLYWHEEL, result)
