from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from db.dao.transactions import TransactionDAO
from db.models.transaction import Transaction
from db.models.user import User
from local_identity import resolve_local_user


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
    """Look up the transaction created by the normalizer and update ML fields.

    The normalizer stage creates the transaction and sets transaction_id.
    Downstream services (posting, resolution) call this to fetch it and
    attach ML enrichment data. No re-normalization is performed.
    """
    user = resolve_local_user(db, message.get("user_id"))
    transaction_id = message.get("transaction_id")

    if not transaction_id:
        raise ValueError("message is missing transaction_id — normalizer should have set it")

    transaction = TransactionDAO.get_by_id(db, transaction_id)
    if transaction is None:
        raise ValueError(f"transaction {transaction_id} not found — normalizer should have created it")

    TransactionDAO.update_ml_enrichment(
        db,
        transaction.id,
        intent_label=message.get("intent_label"),
        entities=message.get("entities"),
        bank_category=message.get("bank_category"),
        cca_class_match=message.get("cca_class_match"),
    )
    return user, transaction

