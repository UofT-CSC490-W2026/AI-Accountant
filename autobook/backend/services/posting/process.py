import logging
import uuid
from datetime import datetime, timezone

from config import get_settings
from queues import enqueue, publish_sync

logger = logging.getLogger(__name__)
settings = get_settings()


def _compute_parse_time_ms(message: dict) -> int | None:
    submitted_at = message.get("submitted_at")
    if not submitted_at:
        return None
    try:
        start = datetime.fromisoformat(submitted_at)
        return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    except (ValueError, TypeError):
        return None


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: write journal entry to database
    journal_entry_id = f"je_{uuid.uuid4().hex[:8]}"
    parse_time_ms = _compute_parse_time_ms(message)

    publish_sync("entry.posted", {
        "type": "entry.posted",
        "journal_entry_id": journal_entry_id,
        "parse_id": message.get("parse_id"),
        "input_text": message.get("input_text"),
        "user_id": message.get("user_id"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "confidence": message.get("confidence"),
        "explanation": message.get("explanation"),
        "status": "auto_posted",
        "proposed_entry": message.get("proposed_entry"),
        "parse_time_ms": parse_time_ms,
    })

    result = {**message, "journal_entry_id": journal_entry_id}
    enqueue(settings.SQS_QUEUE_FLYWHEEL, result)
