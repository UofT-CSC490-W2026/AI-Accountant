from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

ASSET_KEYWORDS = {
    "laptop": "laptop",
    "computer": "computer",
    "equipment": "equipment",
    "printer": "printer",
    "desk": "desk",
    "chair": "chair",
}

INTENT_RULES: list[tuple[str, tuple[str, ...], float]] = [
    ("transfer", ("transfer", "e-transfer", "etransfer", "moved money"), 0.82),
    ("asset_purchase", tuple(ASSET_KEYWORDS.keys()), 0.95),
    ("software_subscription", ("software", "subscription", "saas", "notion", "slack", "figma", "quickbooks"), 0.93),
    ("rent_expense", ("rent", "lease"), 0.94),
    ("meals_entertainment", ("meal", "lunch", "dinner", "restaurant", "coffee", "cafe"), 0.89),
    ("professional_fees", ("contractor", "consultant", "professional", "lawyer", "accountant", "bookkeeper"), 0.9),
    ("bank_fee", ("bank fee", "monthly fee", "service charge", "nsf fee", "wire fee"), 0.9),
]

AMOUNT_PATTERNS = (
    r"\$\s*([\d,]+(?:\.\d+)?)",
    r"\b(?:for|paid|payment|invoice|bill|charge|charged)\s+\$?\s*([\d,]+(?:\.\d+)?)\b",
)

DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
)
SOURCE_ALIASES = {
    "manual": "manual_text",
    "manual_text": "manual_text",
    "csv": "csv_upload",
    "csv_upload": "csv_upload",
    "pdf": "pdf_upload",
    "pdf_upload": "pdf_upload",
    "upload": "upload",
    "bank_feed": "bank_feed",
}
UPLOAD_SOURCES = {"upload", "csv_upload", "pdf_upload"}
MANUAL_SOURCES = {"manual_text"}


def _normalize_party_value(candidate: str) -> str:
    return " ".join(token[:1].upper() + token[1:].lower() for token in candidate.split())


@dataclass(frozen=True)
class ClassificationResult:
    label: str | None
    confidence: float | None


@dataclass(frozen=True)
class EntityExtractionResult:
    amount: float | None
    vendor: str | None
    asset_name: str | None
    entities: dict


class BaselineInferenceService:
    """Rule-based baseline used until trained models replace these methods."""

    def canonicalize_source(self, source: str | None) -> str:
        normalized = str(source or "manual_text").strip().lower()
        return SOURCE_ALIASES.get(normalized, normalized or "manual_text")

    def normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def extract_amount(self, message: dict, text: str) -> float | None:
        existing = message.get("amount")
        if existing is not None:
            try:
                return float(existing)
            except (TypeError, ValueError):
                return None

        amount_mentions = list(message.get("amount_mentions") or [])
        if len(amount_mentions) == 1:
            value = amount_mentions[0].get("value")
            if value is not None:
                return float(value)
        if len(amount_mentions) > 1:
            return None

        for pattern in AMOUNT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match is not None:
                return float(match.group(1).replace(",", ""))

        for token in re.findall(r"\b[\d,]+(?:\.\d+)?\b", text):
            normalized = token.replace(",", "")
            if re.fullmatch(r"(19|20)\d{2}", normalized):
                continue
            return float(normalized)
        return None

    def extract_vendor(self, text: str) -> str | None:
        patterns = [
            r"\bfrom\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s*$)",
            r"\bpaid\s+([a-z][a-z0-9&.' -]+?)(?:\s+\d|\s+for|\s*$)",
            r"\bbought\s+(?:a|an)?\s*([a-z][a-z0-9&.' -]+?)(?:\s+for|\s*$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match is not None:
                return match.group(1).strip(" .").title()
        return None

    def select_party_mention(self, message: dict) -> str | None:
        mentions = list(message.get("party_mentions") or [])
        if len(mentions) == 1:
            value = mentions[0].get("value")
            return _normalize_party_value(str(value)) if value is not None else None
        return None

    def extract_asset_name(self, text: str) -> str | None:
        lowered = text.lower()
        for keyword, label in ASSET_KEYWORDS.items():
            if keyword in lowered:
                return label
        return None

    def extract_quantity(self, message: dict) -> int | None:
        mentions = list(message.get("quantity_mentions") or [])
        if len(mentions) == 1:
            value = mentions[0].get("value")
            if value is not None:
                return int(value)
        return None

    def extract_mentioned_date(self, text: str) -> str | None:
        mentions = []
        if text:
            for pattern in DATE_PATTERNS:
                match = re.search(pattern, text)
                if match is not None:
                    return match.group(1)
        return None

    def extract_mentioned_date_from_message(self, message: dict, text: str) -> str | None:
        mentions = list(message.get("date_mentions") or [])
        if len(mentions) >= 1:
            value = mentions[0].get("value")
            return str(value) if value is not None else None
        for pattern in DATE_PATTERNS:
            match = re.search(pattern, text)
            if match is not None:
                return match.group(1)
        return None

    def extract_transfer_destination(self, text: str) -> str | None:
        match = re.search(r"\bto\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s*$)", text, re.IGNORECASE)
        if match is None:
            return None
        candidate = match.group(1).strip(" .")
        if candidate.lower() in {"cash", "expense", "equipment"}:
            return None
        return candidate.title()

    def classify_intent(self, text: str, source: str) -> ClassificationResult:
        lowered = text.lower()

        for label, keywords, confidence in INTENT_RULES:
            if any(keyword in lowered for keyword in keywords):
                return ClassificationResult(label, confidence)
        if source in UPLOAD_SOURCES:
            return ClassificationResult("bank_transaction", 0.7)

        return ClassificationResult("general_expense", 0.6)

    def classify_bank_transaction(self, text: str, intent_label: str | None) -> ClassificationResult:
        lowered = text.lower()

        if intent_label == "transfer":
            return ClassificationResult("transfer", 0.88)
        if intent_label == "asset_purchase":
            return ClassificationResult("equipment", 0.93)
        if intent_label == "software_subscription":
            return ClassificationResult("software_subscription", 0.92)
        if intent_label == "rent_expense":
            return ClassificationResult("rent", 0.94)
        if intent_label == "meals_entertainment":
            return ClassificationResult("meals_entertainment", 0.87)
        if intent_label == "professional_fees":
            return ClassificationResult("professional_fees", 0.9)
        if intent_label == "bank_fee" or "fee" in lowered:
            return ClassificationResult("bank_fees", 0.9)

        return ClassificationResult(None, None)

    def match_cca_class(self, intent_label: str | None, asset_name: str | None) -> ClassificationResult:
        if intent_label != "asset_purchase":
            return ClassificationResult(None, None)
        if asset_name in {"laptop", "computer", "printer"}:
            return ClassificationResult("class_50", 0.91)
        if asset_name in {"desk", "chair"}:
            return ClassificationResult("class_8", 0.85)
        return ClassificationResult("class_8", 0.72)

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        amount = self.extract_amount(message, text)
        vendor = message.get("counterparty") or self.select_party_mention(message) or self.extract_vendor(text)
        asset_name = self.extract_asset_name(text)
        mentioned_date = self.extract_mentioned_date_from_message(message, text)
        transfer_destination = self.extract_transfer_destination(text)
        quantity = self.extract_quantity(message)

        entities = dict(message.get("entities") or {})
        if amount is not None:
            entities.setdefault("amount", amount)
        if vendor is not None:
            entities.setdefault("vendor", vendor)
        if asset_name is not None:
            entities.setdefault("asset_name", asset_name)
        if quantity is not None:
            entities.setdefault("quantity", quantity)
        if mentioned_date is not None:
            entities.setdefault("mentioned_date", mentioned_date)
        if transfer_destination is not None:
            entities.setdefault("transfer_destination", transfer_destination)
        amount_mentions = list(message.get("amount_mentions") or [])
        if amount_mentions:
            entities.setdefault("amount_mentions", amount_mentions)
        party_mentions = list(message.get("party_mentions") or [])
        if party_mentions:
            entities.setdefault("party_mentions", party_mentions)
        quantity_mentions = list(message.get("quantity_mentions") or [])
        if quantity_mentions:
            entities.setdefault("quantity_mentions", quantity_mentions)
        entities.setdefault("source_text", text)
        entities.setdefault("date", str(message.get("transaction_date") or date.today()))

        return EntityExtractionResult(
            amount=amount,
            vendor=vendor,
            asset_name=asset_name,
            entities=entities,
        )

    def score_confidence(self, *scores: float | None) -> float:
        valid_scores = [score for score in scores if score is not None]
        return round(sum(valid_scores) / len(valid_scores), 3) if valid_scores else 0.6

    def enrich(self, message: dict) -> dict:
        text = str(
            message.get("input_text")
            or message.get("description")
            or ""
        )
        normalized_text = self.normalize_text(text)
        source = self.canonicalize_source(message.get("source"))

        entity_result = self.extract_entities(message, text)
        intent = self.classify_intent(text, source)
        bank_category = self.classify_bank_transaction(text, intent.label)
        cca_class = self.match_cca_class(intent.label, entity_result.asset_name)
        ml_score = self.score_confidence(intent.confidence, bank_category.confidence, cca_class.confidence)

        confidence = dict(message.get("confidence") or {})
        confidence["ml"] = ml_score

        return {
            **message,
            "normalized_text": normalized_text,
            "input_type": source if source not in MANUAL_SOURCES else "manual_text",
            "transaction_date": str(message.get("transaction_date") or date.today()),
            "amount": entity_result.amount,
            "counterparty": entity_result.vendor,
            "intent_label": intent.label,
            "entities": entity_result.entities,
            "bank_category": bank_category.label,
            "cca_class_match": cca_class.label,
            "confidence": confidence,
        }


@lru_cache
def get_inference_service() -> BaselineInferenceService:
    return BaselineInferenceService()


def enrich_message(message: dict) -> dict:
    return get_inference_service().enrich(message)
