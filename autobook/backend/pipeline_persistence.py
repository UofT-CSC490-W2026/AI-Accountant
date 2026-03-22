from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from db.dao.transactions import TransactionDAO
from db.models.transaction import Transaction
from db.models.user import User
from local_identity import resolve_local_user
from normalization.service import normalize_message


def coerce_transaction_date(value) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return date.today()


def ensure_transaction_for_message(db: Session, message: dict) -> tuple[User, Transaction]:
    user = resolve_local_user(db, message.get("user_id"))
    normalized = normalize_message(message)
    transaction_id = message.get("transaction_id")
    transaction = TransactionDAO.get_by_id(db, transaction_id) if transaction_id else None

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

    TransactionDAO.update_ml_enrichment(
        db,
        transaction.id,
        intent_label=message.get("intent_label"),
        entities=message.get("entities"),
        bank_category=message.get("bank_category"),
        cca_class_match=message.get("cca_class_match"),
    )
    return user, transaction
