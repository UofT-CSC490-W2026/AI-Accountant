from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime


AMOUNT_PATTERNS = (
    r"\$\s*([\d,]+(?:\.\d+)?)",
    r"\b(?:for|paid|payment|invoice|bill|charge|charged)\s+\$?\s*([\d,]+(?:\.\d+)?)\b",
)

DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
)

NON_PARTY_TOKENS = {"invoice", "tax", "cash", "inventory", "rent", "payment", "expense"}
NON_QUANTITY_UNITS = {"cash", "cad", "usd", "dollars", "tax", "invoice"}
STRUCTURED_AMOUNT_SOURCES = {"csv", "csv_upload", "bank_feed"}


def _normalize_party_value(candidate: str) -> str:
    return " ".join(token[:1].upper() + token[1:].lower() for token in candidate.split())


@dataclass(frozen=True)
class NormalizedTransactionCandidate:
    description: str
    normalized_description: str
    amount: float | None
    amount_confident: bool
    currency: str
    transaction_date: str
    source: str
    counterparty: str | None
    amount_mentions: list[dict]
    date_mentions: list[dict]
    party_mentions: list[dict]
    quantity_mentions: list[dict]


class NormalizationService:
    def normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    def extract_amount_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[float] = set()
        for pattern in AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = float(match.group(1).replace(",", ""))
                raw_value = match.group(1).strip()
                normalized_text = f"${raw_value}" if "$" in match.group(0) else raw_value
                if value not in seen:
                    seen.add(value)
                    mentions.append(
                        {
                            "text": normalized_text,
                            "value": value,
                        }
                    )

        scrubbed = text
        for pattern in DATE_PATTERNS:
            scrubbed = re.sub(pattern, " ", scrubbed)

        for token in re.findall(r"\b[\d,]+(?:\.\d+)?\b", scrubbed):
            normalized = token.replace(",", "")
            if re.fullmatch(r"(19|20)\d{2}", normalized):
                continue
            value = float(normalized)
            if value not in seen:
                seen.add(value)
                mentions.append({"text": token, "value": value})

        return mentions

    def extract_date_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[str] = set()
        for pattern in DATE_PATTERNS:
            for match in re.finditer(pattern, text):
                raw = match.group(1)
                if raw in seen:
                    continue
                seen.add(raw)
                try:
                    normalized = (
                        datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
                        if "/" in raw
                        else date.fromisoformat(raw).isoformat()
                    )
                except ValueError:
                    normalized = raw
                mentions.append({"text": raw, "value": normalized})
        return mentions

    def extract_party_mentions(self, text: str) -> list[dict]:
        patterns = [
            r"\bfrom\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s+and|\s*$)",
            r"\bpaid\s+([a-z][a-z0-9&.' -]+?)(?:\s+\d|\s+for|\s+and|\s*$)",
            r"\bto\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s+and|\s*$)",
        ]
        mentions: list[dict] = []
        seen: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                candidate = match.group(1).strip(" .")
                normalized = _normalize_party_value(candidate)
                if normalized.lower() in NON_PARTY_TOKENS:
                    continue
                if normalized in seen:
                    continue
                seen.add(normalized)
                mentions.append({"text": candidate, "value": normalized})
        return mentions

    def extract_quantity_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[tuple[int, str]] = set()
        for match in re.finditer(r"\b(\d+)\s+([a-z][a-z0-9-]*)\b", text, re.IGNORECASE):
            quantity = int(match.group(1))
            noun = match.group(2).lower()
            if noun in NON_QUANTITY_UNITS:
                continue
            key = (quantity, noun)
            if key in seen:
                continue
            seen.add(key)
            mentions.append(
                {
                    "text": match.group(0),
                    "value": quantity,
                    "unit": noun,
                }
            )
        return mentions

    def extract_amount(
        self,
        message: dict,
        amount_mentions: list[dict],
    ) -> tuple[float | None, bool]:
        existing = message.get("amount")
        if existing is not None:
            try:
                return float(existing), True
            except (TypeError, ValueError):
                pass

        source = str(message.get("source") or "manual_text")
        if source in STRUCTURED_AMOUNT_SOURCES and len(amount_mentions) == 1:
            return float(amount_mentions[0]["value"]), True
        return None, False

    def extract_counterparty(
        self,
        message: dict,
        party_mentions: list[dict],
    ) -> str | None:
        explicit = message.get("counterparty")
        if explicit:
            return str(explicit)
        source = str(message.get("source") or "manual_text")
        if source in STRUCTURED_AMOUNT_SOURCES and len(party_mentions) == 1:
            return str(party_mentions[0]["value"])
        return None

    def extract_transaction_date(self, message: dict, text: str) -> str:
        existing = message.get("transaction_date")
        if existing:
            return str(existing)

        for pattern in DATE_PATTERNS:
            match = re.search(pattern, text)
            if match is not None:
                raw = match.group(1)
                try:
                    if "/" in raw:
                        return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
                    return date.fromisoformat(raw).isoformat()
                except ValueError:
                    return raw
        return str(date.today())

    def normalize(self, message: dict) -> NormalizedTransactionCandidate:
        description = str(
            message.get("input_text")
            or message.get("description")
            or (f"Uploaded file: {message.get('filename')}" if message.get("filename") else "Autobook transaction")
        )
        normalized_description = self.normalize_text(description)
        amount_mentions = self.extract_amount_mentions(description)
        date_mentions = self.extract_date_mentions(description)
        party_mentions = self.extract_party_mentions(description)
        quantity_mentions = self.extract_quantity_mentions(description)
        amount, amount_confident = self.extract_amount(message, amount_mentions)

        return NormalizedTransactionCandidate(
            description=description,
            normalized_description=normalized_description,
            amount=amount,
            amount_confident=amount_confident,
            currency=str(message.get("currency") or "CAD"),
            transaction_date=self.extract_transaction_date(message, description),
            source=str(message.get("source") or "manual_text"),
            counterparty=self.extract_counterparty(message, party_mentions),
            amount_mentions=amount_mentions,
            date_mentions=date_mentions,
            party_mentions=party_mentions,
            quantity_mentions=quantity_mentions,
        )


def normalize_message(message: dict) -> NormalizedTransactionCandidate:
    return NormalizationService().normalize(message)
