import logging
from datetime import datetime, timezone

from config import get_settings
from queues import enqueue, publish_sync

logger = logging.getLogger(__name__)
settings = get_settings()


def _stub_classify(message: dict) -> dict:
    """Stub: simulate LLM classification with confidence, explanation, and proposed entry."""
    import re

    existing_confidence = message.get("confidence", {}).get("overall")
    if existing_confidence is not None:
        return {"confidence": existing_confidence, "explanation": message.get("explanation", ""), "proposed_entry": message.get("proposed_entry")}

    text = message.get("input_text", "")
    amount_match = re.search(r"\$[\d,]+(?:\.\d+)?", text)

    if message.get("source") == "upload" or amount_match:
        amount = float(amount_match.group().replace("$", "").replace(",", "")) if amount_match else 1000.00
        return {
            "confidence": 0.97,
            "explanation": f"[BACKEND STUB] Classified as equipment purchase. Debiting Equipment, crediting Cash for ${amount:.2f}.",
            "proposed_entry": {
                "lines": [
                    {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            },
        }

    return {
        "confidence": 0.45,
        "explanation": f"[BACKEND STUB] Transfer direction is unclear. Unable to determine debit/credit accounts from: \"{text}\".",
        "proposed_entry": {"lines": []},
    }


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: call Bedrock LLM for classification (tier 3)
    classification = _stub_classify(message)
    confidence = classification["confidence"]
    enriched = {**message, "confidence": {"overall": confidence}, "explanation": classification["explanation"], "proposed_entry": classification["proposed_entry"]}

    if confidence >= settings.AUTO_POST_THRESHOLD:
        enqueue(settings.SQS_QUEUE_POSTING, enriched)
    else:
        publish_sync("clarification.created", {
            "type": "clarification.created",
            "parse_id": message.get("parse_id"),
            "input_text": message.get("input_text"),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })
        enqueue(settings.SQS_QUEUE_RESOLUTION, message)
