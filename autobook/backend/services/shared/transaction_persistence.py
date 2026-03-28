from __future__ import annotations

"""Shared helpers for creating/updating the canonical transaction row.

Worker stages call into this module so they all persist against the same
transaction record instead of re-implementing partial insert/update logic.
"""

from datetime import date

from sqlalchemy.orm import Session

from db.dao.transactions import TransactionDAO
from db.models.transaction import Transaction
from db.models.user import User
from local_identity import resolve_local_user
from services.shared.normalization import normalize_message


def coerce_transaction_date(value) -> date:
    """Best-effort conversion to a concrete date for transaction storage."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def ensure_transaction_for_message(db: Session, message: dict) -> tuple[User, Transaction]:
    """Upsert the transaction backing a pipeline message and attach ML fields.

    The early pipeline may create the transaction for the first time, while later
    stages may revisit the same record with better normalized or inferred data.
    """
    user = resolve_local_user(db, message.get("user_id"))
    normalized = normalize_message(message)
    transaction_id = message.get("transaction_id")
    transaction = TransactionDAO.get_by_id(db, transaction_id) if transaction_id else None

    # Create the canonical transaction the first time we see this parse, or
    # refresh its normalized fields when a later stage already has the row id.
    if transaction is None:
        transaction = TransactionDAO.insert(
            db=db,
            user_id=user.id,
            description=normalized.description,
            normalized_description=normalized.normalized_description,
            amount=message.get("amount") if message.get("amount") is not None else normalized.amount,
            currency=normalized.currency,
            date=coerce_transaction_date(message.get("transaction_date") or normalized.transaction_date),
            source=normalized.source,
            counterparty=message.get("counterparty") or normalized.counterparty,
            amount_mentions=normalized.amount_mentions,
            date_mentions=normalized.date_mentions,
            party_mentions=normalized.party_mentions,
            quantity_mentions=normalized.quantity_mentions,
        )
    else:
        TransactionDAO.update_normalized_fields(
            db,
            transaction.id,
            description=normalized.description,
            normalized_description=normalized.normalized_description,
            amount=message.get("amount") if message.get("amount") is not None else normalized.amount,
            currency=normalized.currency,
            date=coerce_transaction_date(message.get("transaction_date") or normalized.transaction_date),
            source=normalized.source,
            counterparty=message.get("counterparty") or normalized.counterparty,
            amount_mentions=normalized.amount_mentions,
            date_mentions=normalized.date_mentions,
            party_mentions=normalized.party_mentions,
            quantity_mentions=normalized.quantity_mentions,
        )

    # ML enrichment is stored separately so later stages can add intent/entity
    # predictions without rebuilding the base transaction row.
    TransactionDAO.update_ml_enrichment(
        db,
        transaction.id,
        intent_label=message.get("intent_label"),
        entities=message.get("entities"),
        bank_category=message.get("bank_category"),
        cca_class_match=message.get("cca_class_match"),
    )
    return user, transaction

