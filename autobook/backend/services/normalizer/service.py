import logging

from config import get_settings
from db.connection import SessionLocal
from db.dao.transactions import TransactionDAO
from local_identity import resolve_local_user
from services.normalizer.logic import normalize_message
from services.shared.parse_status import set_status_sync
from services.shared.transaction_persistence import coerce_transaction_date
from queues import sqs
from queues.pubsub import pub

logger = logging.getLogger(__name__)
settings = get_settings()


def _persist_canonical_transaction(message: dict) -> dict:
    db = SessionLocal()
    try:
        user = resolve_local_user(db, message.get("user_id"))
        normalized = normalize_message(message)
        transaction = TransactionDAO.insert(
            db=db,
            user_id=user.id,
            description=normalized.description,
            normalized_description=normalized.normalized_description,
            amount=normalized.amount,
            currency=normalized.currency,
            date=coerce_transaction_date(normalized.transaction_date),
            source=normalized.source,
            counterparty=normalized.counterparty,
            amount_mentions=normalized.amount_mentions,
            date_mentions=normalized.date_mentions,
            party_mentions=normalized.party_mentions,
            quantity_mentions=normalized.quantity_mentions,
        )
        db.commit()
        return {
            **message,
            "transaction_id": str(transaction.id),
            "description": normalized.description,
            "normalized_description": normalized.normalized_description,
            "transaction_date": normalized.transaction_date,
            "amount": normalized.amount,
            "currency": normalized.currency,
            "source": normalized.source,
            "counterparty": normalized.counterparty,
            "amount_mentions": normalized.amount_mentions,
            "date_mentions": normalized.date_mentions,
            "party_mentions": normalized.party_mentions,
            "quantity_mentions": normalized.quantity_mentions,
            "normalizer": {
                "amount_confident": normalized.amount_confident,
            },
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _normalize_only(message: dict) -> dict:
    """Normalize without persisting to DB."""
    normalized = normalize_message(message)
    return {
        **message,
        "description": normalized.description,
        "normalized_description": normalized.normalized_description,
        "transaction_date": normalized.transaction_date,
        "amount": normalized.amount,
        "currency": normalized.currency,
        "source": normalized.source,
        "counterparty": normalized.counterparty,
        "amount_mentions": normalized.amount_mentions,
        "date_mentions": normalized.date_mentions,
        "party_mentions": normalized.party_mentions,
        "quantity_mentions": normalized.quantity_mentions,
        "normalizer": {"amount_confident": normalized.amount_confident},
    }


def execute(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    set_status_sync(
        parse_id=message["parse_id"],
        user_id=message["user_id"],
        status="processing",
        stage="normalizer",
        input_text=message.get("input_text") or message.get("filename"),
    )
    run_type = message.get("run_type", "full_pipeline")
    store = message.get("store_transaction", True)

    if store:
        result = _persist_canonical_transaction(message)
    else:
        result = _normalize_only(message)

    if run_type == "normalizer":
        pub.pipeline_result(
            parse_id=message["parse_id"],
            user_id=message["user_id"],
            stage="normalizer",
            result=result,
        )
        return

    sqs.enqueue.precedent(result)
