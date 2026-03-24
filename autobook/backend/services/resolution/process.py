import logging
from datetime import datetime, timezone

from config import get_settings
from db.connection import SessionLocal
from db.dao.clarifications import ClarificationDAO
from queues import sqs
from queues.redis import publish_sync
from services.shared.transaction_persistence import ensure_transaction_for_message

logger = logging.getLogger(__name__)
settings = get_settings()


def _is_resolved(message: dict) -> bool:
    clarification = dict(message.get("clarification") or {})
    status = clarification.get("status") or message.get("clarification_status") or message.get("action")
    if status is None:
        return False
    return str(status).lower() in {"approved", "resolve", "resolved", "posted", "post"}


def _is_rejected(message: dict) -> bool:
    clarification = dict(message.get("clarification") or {})
    status = clarification.get("status") or message.get("clarification_status") or message.get("action")
    if status is None:
        return False
    return str(status).lower() in {"reject", "rejected", "discard", "discarded"}


def _persist_pending_clarification(message: dict) -> str:
    db = SessionLocal()
    try:
        user, transaction = ensure_transaction_for_message(db, message)
        task = ClarificationDAO.insert(
            db=db,
            user_id=user.id,
            transaction_id=transaction.id,
            source_text=message.get("input_text") or message.get("normalized_text") or "",
            explanation=message.get("explanation") or "Clarification required",
            confidence=(message.get("confidence") or {}).get("overall") or 0,
            proposed_entry=message.get("proposed_entry"),
            verdict="needs_human_review",
        )
        db.commit()
        return str(task.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    clarification = dict(message.get("clarification") or {})

    if _is_rejected(message):
        publish_sync("clarification.resolved", {
            "type": "clarification.resolved",
            "parse_id": message.get("parse_id"),
            "user_id": message.get("user_id"),
            "input_text": message.get("input_text"),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "status": "rejected",
        })
        return

    if not _is_resolved(message):
        # Current behavior for the placeholder clarification queue:
        # persist the clarification task and do not auto-post it.
        clarification_id = _persist_pending_clarification(message)
        clarification["clarification_id"] = clarification_id
        clarification["status"] = "pending"
        return

    clarification["required"] = False
    clarification["status"] = "resolved"
    result = {**message, "clarification": clarification}

    publish_sync("clarification.resolved", {
        "type": "clarification.resolved",
        "parse_id": message.get("parse_id"),
        "user_id": message.get("user_id"),
        "input_text": message.get("input_text"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "status": "resolved",
        "confidence": message.get("confidence"),
        "explanation": message.get("explanation"),
        "proposed_entry": message.get("proposed_entry"),
    })
    sqs.enqueue.posting(result)
