import logging
import uuid
from datetime import datetime, timezone

from config import get_settings
from queues import enqueue, publish_sync

logger = logging.getLogger(__name__)
settings = get_settings()


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: write journal entry to database
    journal_entry_id = f"je_{uuid.uuid4().hex[:8]}"

    publish_sync("entry.posted", {
        "type": "entry.posted",
        "journal_entry_id": journal_entry_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    })

    result = {**message, "journal_entry_id": journal_entry_id}
    enqueue(settings.SQS_QUEUE_FLYWHEEL, result)
