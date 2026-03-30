"""Normalization helpers for the ingest path.

A5 part 4 focuses on this module because it performs the regex-heavy extraction
that every parse request depends on before downstream classification and posting.
The targeted tests in `tests/services/shared/test_normalization.py` cover:

- duplicate amount matches and date scrubbing, because false positives here can
  turn a date or repeated token into the transaction amount
- explicit message overrides and invalid explicit values, because upstream
  routes may provide partially-normalized payloads
- slash-format and invalid dates, because uploaded bank text mixes formats
- party-token filtering and explicit counterparty precedence, because routing
  should not treat generic nouns like "cash" as vendors
- quantity-unit filtering, because numeric mentions often include currencies or
  invoice references that should not become item counts
- fallback description/currency/date behavior, because uploads may arrive with
  filenames instead of free-form text
"""

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
CANONICAL_SOURCE_ALIASES = {
    "manual": "manual_text",
    "manual_text": "manual_text",
    "csv": "csv_upload",
    "csv_upload": "csv_upload",
    "pdf": "pdf_upload",
    "pdf_upload": "pdf_upload",
    "upload": "upload",
    "bank_feed": "bank_feed",
}

AMOUNT_REGEXES = tuple(re.compile(pattern, re.IGNORECASE) for pattern in AMOUNT_PATTERNS)
DATE_REGEXES = tuple(re.compile(pattern) for pattern in DATE_PATTERNS)
DATE_SCRUB_REGEX = re.compile("|".join(f"(?:{pattern})" for pattern in DATE_PATTERNS))
NUMERIC_TOKEN_REGEX = re.compile(r"\b[\d,]+(?:\.\d+)?\b")
YEAR_TOKEN_REGEX = re.compile(r"(19|20)\d{2}")
PARTY_REGEXES = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bfrom\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s+and|\s*$)",
        r"\bpaid\s+([a-z][a-z0-9&.' -]+?)(?:\s+\d|\s+for|\s+and|\s*$)",
        r"\bto\s+([a-z][a-z0-9&.' -]+?)(?:\s+for|\s+and|\s*$)",
    )
)
QUANTITY_REGEX = re.compile(r"\b(\d+)\s+([a-z][a-z0-9-]*)\b", re.IGNORECASE)


def _normalize_party_value(candidate: str) -> str:
    return " ".join(token[:1].upper() + token[1:].lower() for token in candidate.split())


def _normalize_date_string(raw: str) -> str:
    try:
        if "/" in raw:
            return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return raw


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
    def canonicalize_source(self, source: str | None) -> str:
        normalized = str(source or "manual_text").strip().lower()
        return CANONICAL_SOURCE_ALIASES.get(normalized, normalized or "manual_text")

    def normalize_text(self, text: str) -> str:
        return " ".join(text.lower().split())

    def extract_amount_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[float] = set()
        for pattern in AMOUNT_REGEXES:
            for match in pattern.finditer(text):
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

        scrubbed = DATE_SCRUB_REGEX.sub(" ", text)
        for token in NUMERIC_TOKEN_REGEX.findall(scrubbed):
            normalized = token.replace(",", "")
            if YEAR_TOKEN_REGEX.fullmatch(normalized):
                continue
            value = float(normalized)
            if value not in seen:
                seen.add(value)
                mentions.append({"text": token, "value": value})

        return mentions

    def extract_date_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[str] = set()
        for pattern in DATE_REGEXES:
            for match in pattern.finditer(text):
                raw = match.group(1)
                if raw in seen:
                    continue
                seen.add(raw)
                mentions.append({"text": raw, "value": _normalize_date_string(raw)})
        return mentions

    def extract_party_mentions(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        seen: set[str] = set()
        for pattern in PARTY_REGEXES:
            for match in pattern.finditer(text):
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
        for match in QUANTITY_REGEX.finditer(text):
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

        if len(amount_mentions) == 1:
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
        if len(party_mentions) == 1:
            return str(party_mentions[0]["value"])
        return None

    def extract_transaction_date(
        self,
        message: dict,
        text: str,
        date_mentions: list[dict] | None = None,
    ) -> str:
        existing = message.get("transaction_date")
        if existing:
            return str(existing)

        if date_mentions:
            return str(date_mentions[0]["value"])

        for pattern in DATE_REGEXES:
            match = pattern.search(text)
            if match is not None:
                return _normalize_date_string(match.group(1))
        return str(date.today())

    def normalize(self, message: dict) -> NormalizedTransactionCandidate:
        source = self.canonicalize_source(message.get("source"))
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
            transaction_date=self.extract_transaction_date(message, description, date_mentions),
            source=source,
            counterparty=self.extract_counterparty(message, party_mentions),
            amount_mentions=amount_mentions,
            date_mentions=date_mentions,
            party_mentions=party_mentions,
            quantity_mentions=quantity_mentions,
        )


def normalize_message(message: dict) -> NormalizedTransactionCandidate:
    return NormalizationService().normalize(message)
