import logging
from datetime import datetime, timezone

from accounting_engine import build_rule_based_entry
from config import get_settings
from queues import enqueue, publish_sync

logger = logging.getLogger(__name__)
settings = get_settings()


def _coerce_confidence(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _reason_over_ml_output(message: dict) -> dict:
    text = str(message.get("input_text") or message.get("description") or "").lower()
    current_confidence = _coerce_confidence((message.get("confidence") or {}).get("ml"), default=0.0)
    entities = dict(message.get("entities") or {})

    inferred_intent = message.get("intent_label")
    inferred_bank_category = message.get("bank_category")
    explanation = "Structured reasoning could not raise confidence above the clarification threshold."
    llm_confidence = current_confidence

    if (
        inferred_intent == "asset_purchase"
        and entities.get("amount") is not None
        and entities.get("asset_name")
    ):
        inferred_bank_category = inferred_bank_category or "equipment"
        llm_confidence = max(current_confidence, 0.97)
        explanation = "Structured reasoning confirmed a clear asset purchase from the extracted amount and asset name."
    elif (
        inferred_intent == "software_subscription"
        and entities.get("amount") is not None
        and (entities.get("vendor") or "subscription" in text)
    ):
        inferred_bank_category = inferred_bank_category or "software_subscription"
        llm_confidence = max(current_confidence, 0.96)
        explanation = "Structured reasoning confirmed a software subscription from the extracted vendor and amount."
    elif "transfer" in text and inferred_intent in {None, "general_expense", "bank_transaction"}:
        inferred_intent = "transfer"
        inferred_bank_category = "transfer"
        llm_confidence = max(current_confidence, 0.55)
        explanation = "Structured reasoning confirmed this is a transfer, but the destination account is still unclear."
    elif "fee" in text and inferred_bank_category is None:
        inferred_intent = "bank_fee"
        inferred_bank_category = "bank_fees"
        llm_confidence = max(current_confidence, 0.9)
        explanation = "Structured reasoning resolved the transaction as a bank fee."
    elif "subscription" in text and inferred_intent in {None, "general_expense", "bank_transaction"}:
        inferred_intent = "software_subscription"
        inferred_bank_category = "software_subscription"
        llm_confidence = max(current_confidence, 0.94)
        explanation = "Structured reasoning resolved the transaction as a software subscription."
    elif "rent" in text and inferred_intent in {None, "general_expense", "bank_transaction"}:
        inferred_intent = "rent_expense"
        inferred_bank_category = "rent"
        llm_confidence = max(current_confidence, 0.94)
        explanation = "Structured reasoning resolved the transaction as a rent expense."
    elif "contractor" in text and inferred_intent in {None, "general_expense", "bank_transaction"}:
        inferred_intent = "professional_fees"
        inferred_bank_category = "professional_fees"
        llm_confidence = max(current_confidence, 0.9)
        explanation = "Structured reasoning resolved the transaction as a professional-fees expense."

    confidence = dict(message.get("confidence") or {})
    confidence["llm"] = llm_confidence
    confidence["overall"] = llm_confidence

    return {
        **message,
        "intent_label": inferred_intent,
        "bank_category": inferred_bank_category,
        "confidence": confidence,
        "explanation": explanation,
    }


def _apply_rule_engine(message: dict, *, origin_tier: int, explanation_prefix: str) -> dict:
    overall_confidence = _coerce_confidence(
        (message.get("confidence") or {}).get("overall"),
        default=_coerce_confidence((message.get("confidence") or {}).get("ml"), default=0.0),
    )
    rule_result = build_rule_based_entry(
        message,
        confidence=overall_confidence,
        origin_tier=origin_tier,
    )
    clarification_required = (
        overall_confidence < settings.AUTO_POST_THRESHOLD or rule_result.requires_human_review
    )

    explanation = f"{explanation_prefix} {rule_result.explanation}".strip()
    return {
        **message,
        "confidence": {
            **dict(message.get("confidence") or {}),
            "overall": overall_confidence,
        },
        "explanation": explanation,
        "proposed_entry": rule_result.proposed_entry,
        "clarification": {
            "required": clarification_required,
            "clarification_id": None,
            "reason": rule_result.clarification_reason if clarification_required else None,
            "status": "pending" if clarification_required else None,
        },
    }


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    ml_confidence = _coerce_confidence((message.get("confidence") or {}).get("ml"), default=0.0)

    if ml_confidence >= settings.AUTO_POST_THRESHOLD:
        enriched = _apply_rule_engine(
            {
                **message,
                "confidence": {
                    **dict(message.get("confidence") or {}),
                    "overall": ml_confidence,
                },
            },
            origin_tier=2,
            explanation_prefix="ML confidence was high enough to route directly into the rule engine.",
        )
    else:
        reasoned = _reason_over_ml_output(message)
        enriched = _apply_rule_engine(
            reasoned,
            origin_tier=3,
            explanation_prefix=reasoned["explanation"],
        )

    if not enriched["clarification"]["required"]:
        enqueue(settings.SQS_QUEUE_POSTING, enriched)
        return

    publish_sync("clarification.created", {
        "type": "clarification.created",
        "parse_id": enriched.get("parse_id"),
        "input_text": enriched.get("input_text"),
        "user_id": enriched.get("user_id"),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "confidence": enriched.get("confidence"),
        "explanation": enriched.get("explanation"),
        "proposed_entry": enriched.get("proposed_entry"),
    })
    enqueue(settings.SQS_QUEUE_RESOLUTION, enriched)
