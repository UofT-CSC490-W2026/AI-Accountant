from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from db.models.transaction import Transaction


class TransactionDAO:
    @staticmethod
    def insert(
        db: Session,
        user_id,
        description: str,
        normalized_description: str | None,
        amount,
        currency: str,
        date: date,
        source: str,
        counterparty: str | None,
        amount_mentions: list[dict] | None = None,
        date_mentions: list[dict] | None = None,
        party_mentions: list[dict] | None = None,
        quantity_mentions: list[dict] | None = None,
    ) -> Transaction:
        set_current_user_context(db, user_id)
        transaction = Transaction(
            user_id=user_id,
            description=description,
            normalized_description=normalized_description,
            amount=amount,
            currency=currency,
            date=date,
            source=source,
            counterparty=counterparty,
            amount_mentions=amount_mentions,
            date_mentions=date_mentions,
            party_mentions=party_mentions,
            quantity_mentions=quantity_mentions,
        )
        db.add(transaction)
        db.flush()
        return transaction

    @staticmethod
    def update_normalized_fields(
        db: Session,
        transaction_id,
        *,
        description: str | None = None,
        normalized_description: str | None = None,
        amount=None,
        currency: str | None = None,
        date: date | None = None,
        source: str | None = None,
        counterparty: str | None = None,
        amount_mentions: list[dict] | None = None,
        date_mentions: list[dict] | None = None,
        party_mentions: list[dict] | None = None,
        quantity_mentions: list[dict] | None = None,
    ) -> Transaction | None:
        transaction = db.get(Transaction, transaction_id)
        if transaction is None:
            return None
        set_current_user_context(db, transaction.user_id)
        if description is not None:
            transaction.description = description
        if normalized_description is not None:
            transaction.normalized_description = normalized_description
        if amount is not None:
            transaction.amount = amount
        if currency is not None:
            transaction.currency = currency
        if date is not None:
            transaction.date = date
        if source is not None:
            transaction.source = source
        if counterparty is not None:
            transaction.counterparty = counterparty
        if amount_mentions is not None:
            transaction.amount_mentions = amount_mentions
        if date_mentions is not None:
            transaction.date_mentions = date_mentions
        if party_mentions is not None:
            transaction.party_mentions = party_mentions
        if quantity_mentions is not None:
            transaction.quantity_mentions = quantity_mentions
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
