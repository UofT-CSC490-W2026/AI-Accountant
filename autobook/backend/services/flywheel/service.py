"""Flywheel worker — tier-based learning after each posted entry.

Actions by origin_tier:
  T1: nothing (already learned)
  T2: pattern store
  T3: pattern store + ML training data
  T4: pattern store + ML training data + RAG + calibration
"""
import logging

from db.connection import SessionLocal, set_current_user_context
from db.dao.training_data import TrainingDataDAO
from local_identity import resolve_local_user
from services.flywheel.calibration import write_calibration_pair
from services.flywheel.pattern_store import write_pattern
from services.flywheel.rag_indexer import index_correction_example, index_positive_example

logger = logging.getLogger(__name__)


def execute(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))

    origin_tier = message.get("origin_tier")
    if origin_tier is None:
        origin_tier = _infer_tier(message)
    origin_tier = int(origin_tier)

    if origin_tier <= 1:
        logger.debug("T1 — nothing to learn")
        return

    db = SessionLocal()
    try:
        user = resolve_local_user(db, message.get("user_id"))
        set_current_user_context(db, user.id)

        # T2+: pattern store
        write_pattern(db, user.id, message)

        # T3+: ML training data
        if origin_tier >= 3:
            TrainingDataDAO.append(
                db=db,
                user_id=user.id,
                transaction_id=message.get("transaction_id"),
                journal_entry_id=message.get("journal_entry_id"),
                origin_tier=origin_tier,
                input_text=message.get("input_text"),
                intent_label=message.get("intent_label"),
                proposed_entry=message.get("proposed_entry"),
            )

        # T4: calibration
        if origin_tier >= 4:
            was_correct = message.get("clarification_action") != "edit"
            write_calibration_pair(db, user.id, message, was_correct=was_correct)

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Flywheel DB write failed for %s", message.get("parse_id"))
        raise
    finally:
        db.close()

    # T4: RAG indexing (outside DB transaction — Qdrant is separate)
    if origin_tier >= 4:
        index_positive_example(message)
        if message.get("clarification_action") == "edit":
            index_correction_example(message)


def _infer_tier(message: dict) -> int:
    """Fallback: infer tier from proposed_entry if origin_tier not set."""
    entry = (message.get("proposed_entry") or {}).get("entry", {})
    return entry.get("origin_tier", 3)
