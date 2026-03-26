import logging

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from config import get_settings
from db.connection import SessionLocal, set_current_user_context
from db.models.journal import JournalEntry
from local_identity import resolve_local_user
from services.precedent.logic import PrecedentCandidate, find_precedent_match

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_precedent_match_payload(match) -> dict:
    return {
        "matched": match.matched,
        "pattern_id": match.pattern_id,
        "confidence": match.confidence,
    }


def _build_precedent_proposed_entry(message: dict, match) -> dict:
    return {
        "entry": {
            "date": message.get("transaction_date"),
            "description": message.get("input_text") or message.get("description") or message.get("normalized_description"),
            "origin_tier": 1,
            "confidence": match.confidence,
            "transaction_id": message.get("transaction_id"),
            "rationale": f"Matched precedent {match.pattern_id} ({match.reasoning}).",
        },
        "lines": [dict(line) for line in match.lines],
    }


def _load_candidates(message: dict) -> list[PrecedentCandidate]:  # pragma: no cover
    db = SessionLocal()
    try:
        user = resolve_local_user(db, message.get("user_id"))
        set_current_user_context(db, user.id)
        stmt = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.lines),
                joinedload(JournalEntry.transaction),
            )
            .where(
                JournalEntry.user_id == user.id,
                JournalEntry.status == "posted",
                JournalEntry.transaction_id.is_not(None),
            )
            .order_by(JournalEntry.posted_at.desc(), JournalEntry.created_at.desc())
            .limit(25)
        )
        entries = list(db.execute(stmt).scalars().unique().all())
    finally:
        db.close()

    current_transaction_id = str(message.get("transaction_id") or "")
    candidates: list[PrecedentCandidate] = []
    for entry in entries:
        if str(entry.transaction_id or "") == current_transaction_id:
            continue
        transaction = entry.transaction
        if transaction is None:
            continue
        candidates.append(
            PrecedentCandidate(
                pattern_id=f"journal_entry:{entry.id}",
                normalized_description=transaction.normalized_description,
                amount=float(transaction.amount) if transaction.amount is not None else None,
                counterparty=transaction.counterparty,
                source=transaction.source,
                lines=[
                    {
                        "account_code": line.account_code,
                        "account_name": line.account_name,
                        "type": line.type,
                        "amount": float(line.amount),
                        "line_order": line.line_order,
                    }
                    for line in entry.lines
                ],
            )
        )
    return candidates


def execute(message: dict) -> dict:
    logger.info("Processing: %s", message.get("parse_id"))
    candidates = _load_candidates(message)
    match = find_precedent_match(message, candidates)

    confidence = dict(message.get("confidence") or {})
    confidence["precedent"] = match.confidence

    result = {
        **message,
        "precedent_match": _build_precedent_match_payload(match),
        "confidence": confidence,
    }

    if match.matched and (match.confidence or 0) >= settings.AUTO_POST_THRESHOLD:
        result = {
            **result,
            "confidence": {**confidence, "overall": match.confidence},
            "proposed_entry": _build_precedent_proposed_entry(message, match),
            "explanation": f"Matched a prior posted journal entry via precedent ({match.reasoning}).",
            "clarification": {"required": False, "clarification_id": None, "reason": None, "status": None},
        }

    return result
