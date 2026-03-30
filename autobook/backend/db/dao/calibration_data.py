"""DAO for confidence_calibration_data table."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.connection import set_current_user_context
from db.models.calibration_data import ConfidenceCalibrationData


class CalibrationDataDAO:
    @staticmethod
    def append(
        db: Session,
        user_id,
        journal_entry_id,
        raw_confidence: float,
        was_correct: bool,
        transaction_type: str | None = None,
    ) -> ConfidenceCalibrationData:
        set_current_user_context(db, user_id)
        row = ConfidenceCalibrationData(
            user_id=user_id,
            journal_entry_id=journal_entry_id,
            raw_confidence=raw_confidence,
            was_correct=was_correct,
            transaction_type=transaction_type,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def count_pending(db: Session) -> int:
        return db.execute(select(func.count(ConfidenceCalibrationData.id))).scalar() or 0
