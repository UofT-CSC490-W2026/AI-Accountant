from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.models.calibration import CalibrationParams


class CalibrationDAO:
    @staticmethod
    def get_latest(db: Session) -> CalibrationParams | None:
        """Return the most recent calibration params (active set)."""
        return (
            db.query(CalibrationParams)
            .order_by(desc(CalibrationParams.created_at))
            .first()
        )

    @staticmethod
    def insert(db: Session, a: float, b: float, sample_count: int) -> CalibrationParams:
        """Append a new calibration snapshot (flywheel calls this after refit)."""
        row = CalibrationParams(a=a, b=b, sample_count=sample_count)
        db.add(row)
        db.flush()
        return row
