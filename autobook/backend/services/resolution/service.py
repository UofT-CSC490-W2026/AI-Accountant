import logging
from datetime import datetime, timezone

from config import get_settings
from db.connection import SessionLocal
from db.dao.clarifications import ClarificationDAO
from db.dao.transactions import TransactionDAO
from queues import sqs
from queues.pubsub import pub
from services.shared.parse_status import set_status_sync

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
        transaction_id = message.get("transaction_id")
        if not transaction_id:
            raise ValueError("message is missing transaction_id — normalizer should have set it")
        transaction = TransactionDAO.get_by_id(db, transaction_id)
        if transaction is None:
            raise ValueError(f"transaction {transaction_id} not found — normalizer should have created it")
        task = ClarificationDAO.insert(
            db=db,
            user_id=transaction.user_id,
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


def execute(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    set_status_sync(
        parse_id=message["parse_id"],
        user_id=message["user_id"],
        status="processing",
        stage="resolution",
        input_text=message.get("input_text"),
    )
    clarification = dict(message.get("clarification") or {})

    if _is_rejected(message):
        set_status_sync(
            parse_id=message["parse_id"],
            user_id=message["user_id"],
            status="rejected",
            stage="resolution",
            input_text=message.get("input_text"),
        )
        pub.clarification_resolved(
            parse_id=message.get("parse_id"),
            user_id=message.get("user_id"),
            status="rejected",
            input_text=message.get("input_text"),
        )
        return

    if not _is_resolved(message):
        # Current behavior for the placeholder clarification queue:
        # persist the clarification task and do not auto-post it.
        clarification_id = _persist_pending_clarification(message)
        clarification["clarification_id"] = clarification_id
        clarification["status"] = "pending"
        set_status_sync(
            parse_id=message["parse_id"],
            user_id=message["user_id"],
            status="needs_clarification",
            stage="resolution",
            input_text=message.get("input_text"),
            explanation=message.get("explanation"),
            confidence=message.get("confidence"),
            proposed_entry=message.get("proposed_entry"),
            clarification_id=clarification_id,
        )
        return

    clarification["required"] = False
    clarification["status"] = "resolved"
    result = {**message, "clarification": clarification}

    pub.clarification_resolved(
        parse_id=message.get("parse_id"),
        user_id=message.get("user_id"),
        status="resolved",
        input_text=message.get("input_text"),
        confidence=message.get("confidence"),
        explanation=message.get("explanation"),
        proposed_entry=message.get("proposed_entry"),
    )
    set_status_sync(
        parse_id=message["parse_id"],
        user_id=message["user_id"],
        status="resolved",
        stage="resolution",
        input_text=message.get("input_text"),
        explanation=message.get("explanation"),
        confidence=message.get("confidence"),
        proposed_entry=message.get("proposed_entry"),
    )
    sqs.enqueue.posting(result)
