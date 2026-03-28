import logging

from config import get_settings
from db.connection import SessionLocal
from services.ml_inference.logic import (
    HybridInferenceService,
    build_inference_service,
    enrich_message,
    get_inference_service,
)
from services.ml_inference.providers.heuristic import BaselineInferenceService

logger = logging.getLogger(__name__)
settings = get_settings()

__all__ = [
    "BaselineInferenceService",
    "HybridInferenceService",
    "build_inference_service",
    "enrich_message",
    "execute",
    "get_inference_service",
]


def _persist_transaction_state(message: dict) -> dict:
    if not message.get("store", True):
        return message

    from services.shared.transaction_persistence import ensure_transaction_for_message

    db = SessionLocal()
    try:
        _, transaction = ensure_transaction_for_message(db, message)
        db.commit()
        return {
            **message,
            "transaction_id": str(transaction.id),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def execute(message: dict) -> dict:
    logger.info("Processing: %s", message.get("parse_id"))
    result = get_inference_service().enrich(message)
    ml_confidence = (result.get("confidence") or {}).get("ml", 0)

    if ml_confidence >= settings.AUTO_POST_THRESHOLD:
        from accounting_engine.rules import build_rule_based_entry

        entry = build_rule_based_entry(result, confidence=ml_confidence, origin_tier=2)
        if not entry.requires_human_review:
            result = {
                **result,
                "confidence": {**result.get("confidence", {}), "overall": ml_confidence},
                "explanation": entry.explanation,
                "proposed_entry": entry.proposed_entry,
            }

    return _persist_transaction_state(result)
