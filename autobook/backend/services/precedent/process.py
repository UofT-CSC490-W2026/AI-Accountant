import logging

from config import get_settings
from queues import sqs

logger = logging.getLogger(__name__)
settings = get_settings()


def enrich_message(message: dict) -> dict:
    precedent_match = dict(message.get("precedent_match") or {})
    precedent_match.setdefault("matched", False)
    precedent_match.setdefault("pattern_id", None)
    precedent_match.setdefault("confidence", None)
    return {**message, "precedent_match": precedent_match}


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: match transaction against precedent patterns (tier 1)
    # On hit: enqueue to posting. On miss: enqueue to ml_inference.
    result = enrich_message(message)
    sqs.enqueue.ml_inference(result)
