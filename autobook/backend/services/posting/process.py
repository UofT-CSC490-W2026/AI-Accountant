import logging
from datetime import datetime, timezone

from config import get_settings
from db.connection import SessionLocal
from db.dao.journal_entries import JournalEntryDAO
from queues import sqs
from queues.redis import publish_sync
from services.shared.transaction_persistence import ensure_transaction_for_message

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


def _normalize_proposed_entry(message: dict) -> dict | None:
    proposed_entry = message.get("proposed_entry")
    if proposed_entry is None:
        return None

    if isinstance(proposed_entry, dict) and "entry" in proposed_entry and "lines" in proposed_entry:
        return proposed_entry

    lines = list(proposed_entry.get("lines", [])) if isinstance(proposed_entry, dict) else []
    return {
        "entry": {
            "date": message.get("transaction_date"),
            "description": message.get("input_text"),
            "origin_tier": 3,
            "confidence": (message.get("confidence") or {}).get("overall"),
            "transaction_id": message.get("transaction_id"),
        },
        "lines": lines,
    }


def _json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value) if hasattr(value, "hex") else value


def _serialize_proposed_entry(proposed_entry: dict | None, journal_entry_id: str | None = None) -> dict | None:
    if proposed_entry is None:
        return None

    entry = {
        key: _json_safe(value)
        for key, value in dict(proposed_entry.get("entry") or {}).items()
    }
    if journal_entry_id is not None:
        entry["journal_entry_id"] = journal_entry_id
    return {
        "entry": entry,
        "lines": list(proposed_entry.get("lines") or []),
    }


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    parse_time_ms = _compute_parse_time_ms(message)
    db = SessionLocal()
    try:
        user, transaction = ensure_transaction_for_message(db, message)
        proposed_entry = _normalize_proposed_entry({**message, "transaction_id": transaction.id})
        if proposed_entry is None:
            raise ValueError("auto-post path requires a proposed entry")

        entry_payload = dict(proposed_entry.get("entry") or {})
        line_payload = list(proposed_entry.get("lines") or [])
        entry_payload.setdefault("transaction_id", transaction.id)
        entry_payload.setdefault("status", "posted")

        journal_entry = JournalEntryDAO.insert_with_lines(db, user.id, entry_payload, line_payload)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    journal_entry_id = str(journal_entry.id)
    proposed_entry = _serialize_proposed_entry(proposed_entry, journal_entry_id=journal_entry_id)

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
        "proposed_entry": proposed_entry,
        "parse_time_ms": parse_time_ms,
    })

    result = {
        **message,
        "transaction_id": str(transaction.id),
        "journal_entry_id": journal_entry_id,
        "proposed_entry": proposed_entry,
    }
    sqs.enqueue.flywheel(result)
