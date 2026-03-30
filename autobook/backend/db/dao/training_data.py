"""DAO for model_training_data table."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from db.models.training_data import ModelTrainingData


class TrainingDataDAO:
    @staticmethod
    def append(
        db: Session,
        user_id,
        transaction_id,
        journal_entry_id,
        origin_tier: int,
        input_text: str | None = None,
        intent_label: str | None = None,
        proposed_entry: dict | None = None,
    ) -> ModelTrainingData:
        set_current_user_context(db, user_id)
        row = ModelTrainingData(
            user_id=user_id,
            transaction_id=transaction_id,
            journal_entry_id=journal_entry_id,
            origin_tier=origin_tier,
            input_text=input_text,
            intent_label=intent_label,
            proposed_entry=proposed_entry,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def count_pending(db: Session) -> int:
        return db.execute(select(func.count(ModelTrainingData.id))).scalar() or 0
