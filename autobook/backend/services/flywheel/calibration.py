"""Write calibration pair for Platt scaling.

Called on T4 (human) resolutions only.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from db.dao.calibration_data import CalibrationDataDAO

logger = logging.getLogger(__name__)


def write_calibration_pair(
    db: Session,
    user_id,
    message: dict,
    was_correct: bool,
) -> None:
    """Append a (raw_confidence, was_correct) pair for future Platt scaling refit."""
    confidence = (message.get("confidence") or {}).get("overall")
    if confidence is None:
        logger.debug("No confidence score — skipping calibration write")
        return

    journal_entry_id = message.get("journal_entry_id")
    if not journal_entry_id:
        return

    transaction_type = message.get("intent_label")

    CalibrationDataDAO.append(
        db=db,
        user_id=user_id,
        journal_entry_id=journal_entry_id,
        raw_confidence=float(confidence),
        was_correct=was_correct,
        transaction_type=transaction_type,
    )
