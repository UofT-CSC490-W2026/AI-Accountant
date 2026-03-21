from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.db.connection import set_current_user_context
from app.models.transaction import Transaction


class TransactionDAO:
    @staticmethod
    def insert(
        db: Session,
        user_id,
        description: str,
        amount,
        currency: str,
        date: date,
        source: str,
        counterparty: str | None,
    ) -> Transaction:
        set_current_user_context(db, user_id)
        transaction = Transaction(
            user_id=user_id,
            description=description,
            amount=amount,
            currency=currency,
            date=date,
            source=source,
            counterparty=counterparty,
        )
        db.add(transaction)
        db.flush()
        return transaction

    @staticmethod
    def update_ml_enrichment(
        db: Session,
        transaction_id,
        intent_label: str | None,
        entities: dict | None,
        bank_category: str | None,
        cca_class_match: str | None,
    ) -> Transaction | None:
        transaction = db.get(Transaction, transaction_id)
        if transaction is None:
            return None
        set_current_user_context(db, transaction.user_id)
        transaction.intent_label = intent_label
        transaction.entities = entities
        transaction.bank_category = bank_category
        transaction.cca_class_match = cca_class_match
        db.flush()
        return transaction

    @staticmethod
    def get_by_id(db: Session, transaction_id) -> Transaction | None:
        return db.get(Transaction, transaction_id)
