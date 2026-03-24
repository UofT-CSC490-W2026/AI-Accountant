import logging
from datetime import date, datetime, timezone

from config import get_settings
from queues import sqs
from queues.redis import publish_sync

logger = logging.getLogger(__name__)
settings = get_settings()
UPLOAD_SOURCES = {"upload", "csv_upload", "pdf_upload"}


def _build_entry_metadata(message: dict, confidence: float) -> dict:
    return {
        "date": str(message.get("transaction_date") or date.today()),
        "description": message.get("input_text") or message.get("normalized_text") or "Autobook generated entry",
        "origin_tier": 3,
        "confidence": confidence,
        "transaction_id": message.get("transaction_id"),
    }


def _normalize_proposed_entry(message: dict, proposed_entry: dict | None, confidence: float) -> dict:
    payload = dict(proposed_entry or {})
    lines = list(payload.get("lines", []))
    entry = dict(payload.get("entry", {}))
    entry.setdefault("date", str(message.get("transaction_date") or date.today()))
    entry.setdefault(
        "description",
        message.get("input_text") or message.get("normalized_text") or "Autobook generated entry",
    )
    entry.setdefault("origin_tier", 3)
    entry.setdefault("confidence", confidence)
    if message.get("transaction_id") is not None:
        entry.setdefault("transaction_id", message.get("transaction_id"))
    return {"entry": entry, "lines": lines}


def _stub_classify(message: dict) -> dict:
    """Stub: simulate LLM classification with confidence, explanation, and proposed entry."""
    import re

    existing_confidence = message.get("confidence", {}).get("overall")
    if existing_confidence is not None:
        return {
            "confidence": existing_confidence,
            "explanation": message.get("explanation", ""),
            "proposed_entry": _normalize_proposed_entry(
                message,
                message.get("proposed_entry"),
                float(existing_confidence),
            ),
        }

    text = message.get("input_text", "")
    amount_match = re.search(r"\$[\d,]+(?:\.\d+)?", text)
    amount = (
        float(amount_match.group().replace("$", "").replace(",", ""))
        if amount_match
        else float(message.get("amount") or 1000.00)
    )
    intent_label = message.get("intent_label")

    if intent_label == "asset_purchase" or message.get("source") in UPLOAD_SOURCES or amount_match:
        confidence = 0.97
        return {
            "confidence": confidence,
            "explanation": f"[BACKEND STUB] Classified as equipment purchase. Debiting Equipment, crediting Cash for ${amount:.2f}.",
            "proposed_entry": _normalize_proposed_entry(message, {
                "entry": _build_entry_metadata(message, confidence),
                "lines": [
                    {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            }, confidence),
        }
    if intent_label == "software_subscription":
        confidence = 0.95
        return {
            "confidence": confidence,
            "explanation": f"[BACKEND STUB] Classified as software expense. Debiting Software & Subscriptions and crediting Cash for ${amount:.2f}.",
            "proposed_entry": _normalize_proposed_entry(message, {
                "entry": _build_entry_metadata(message, confidence),
                "lines": [
                    {"account_code": "5300", "account_name": "Software & Subscriptions", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            }, confidence),
        }
    if intent_label == "rent_expense":
        confidence = 0.95
        return {
            "confidence": confidence,
            "explanation": f"[BACKEND STUB] Classified as rent expense. Debiting Rent Expense and crediting Cash for ${amount:.2f}.",
            "proposed_entry": _normalize_proposed_entry(message, {
                "entry": _build_entry_metadata(message, confidence),
                "lines": [
                    {"account_code": "5200", "account_name": "Rent Expense", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            }, confidence),
        }
    if intent_label == "professional_fees":
        confidence = 0.92
        return {
            "confidence": confidence,
            "explanation": f"[BACKEND STUB] Classified as professional fees. Debiting Professional Fees and crediting Cash for ${amount:.2f}.",
            "proposed_entry": _normalize_proposed_entry(message, {
                "entry": _build_entry_metadata(message, confidence),
                "lines": [
                    {"account_code": "5430", "account_name": "Professional Fees", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            }, confidence),
        }
    if intent_label == "meals_entertainment":
        confidence = 0.9
        return {
            "confidence": confidence,
            "explanation": f"[BACKEND STUB] Classified as meals and entertainment. Debiting Meals & Entertainment and crediting Cash for ${amount:.2f}.",
            "proposed_entry": _normalize_proposed_entry(message, {
                "entry": _build_entry_metadata(message, confidence),
                "lines": [
                    {"account_code": "5400", "account_name": "Meals & Entertainment", "type": "debit", "amount": amount},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": amount},
                ],
            }, confidence),
        }

    confidence = 0.45
    return {
        "confidence": confidence,
        "explanation": f"[BACKEND STUB] Transfer direction is unclear. Unable to determine debit/credit accounts from: \"{text}\".",
        "proposed_entry": _normalize_proposed_entry(
            message,
            {"entry": _build_entry_metadata(message, confidence), "lines": []},
            confidence,
        ),
    }


def process(message: dict) -> None:
    logger.info("Processing: %s", message.get("parse_id"))
    # TODO: call Bedrock LLM for classification (tier 3)
    classification = _stub_classify(message)
    confidence = classification["confidence"]
    confidence_payload = dict(message.get("confidence") or {})
    confidence_payload["overall"] = confidence
    confidence_payload.setdefault("ml", confidence_payload.get("ml"))
    enriched = {
        **message,
        "confidence": confidence_payload,
        "explanation": classification["explanation"],
        "proposed_entry": classification["proposed_entry"],
        "clarification": {
            "required": confidence < settings.AUTO_POST_THRESHOLD,
            "clarification_id": None,
            "reason": classification["explanation"] if confidence < settings.AUTO_POST_THRESHOLD else None,
            "status": "pending" if confidence < settings.AUTO_POST_THRESHOLD else None,
        },
    }

    if confidence >= settings.AUTO_POST_THRESHOLD:
        sqs.enqueue.posting(enriched)
    else:
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
        sqs.enqueue.resolution(enriched)
