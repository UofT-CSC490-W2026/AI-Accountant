import logging

from db.connection import SessionLocal
from db.dao.transactions import TransactionDAO
from local_identity import resolve_local_user
from services.shared.normalization import normalize_message
from services.shared.transaction_persistence import coerce_transaction_date

logger = logging.getLogger(__name__)


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


def execute(message: dict) -> dict:
    logger.info("Processing: %s", message.get("parse_id"))
    store = message.get("store", True)

    if store:
        return _persist_canonical_transaction(message)
    else:
        return _normalize_only(message)
