from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STRING_ENTITY_FIELDS = {
    "vendor": "VENDOR",
    "asset_name": "ASSET_NAME",
    "transfer_destination": "TRANSFER_DESTINATION",
    "mentioned_date": "MENTIONED_DATE",
}


@dataclass(frozen=True)
class LabeledRecord:
    record_id: str
    features: dict
    labels: dict


def load_records(path: Path) -> list[LabeledRecord]:
    records: list[LabeledRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} contains invalid JSON") from exc
            records.append(
                LabeledRecord(
                    record_id=str(payload["record_id"]),
                    features=dict(payload["features"]),
                    labels=dict(payload["labels"]),
                )
            )
    return records


def normalize_runtime_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def feature_text(features: dict) -> str:
    return str(features.get("input_text") or "")


def flattened_runtime_message(record: LabeledRecord) -> dict:
    features = dict(record.features)
    text = feature_text(features)
    return {
        "input_text": text,
        "description": text,
        "normalized_text": str(features.get("normalized_text") or normalize_runtime_text(text)),
        "source": features.get("source"),
        "input_type": features.get("source"),
        "currency": features.get("currency"),
        "transaction_date": features.get("transaction_date"),
        "amount_mentions": list(features.get("amount_mentions") or []),
        "date_mentions": list(features.get("date_mentions") or []),
        "party_mentions": list(features.get("party_mentions") or []),
        "quantity_mentions": list(features.get("quantity_mentions") or []),
        "amount": features.get("amount"),
        "counterparty": features.get("counterparty"),
        "normalized_description": features.get("normalized_description"),
    }


def classifier_text(record: LabeledRecord) -> str:
    features = record.features
    return str(features.get("normalized_text") or features.get("input_text") or "")


def null_safe_label(value) -> str:
    return "__null__" if value is None else str(value)


def label_value(record: LabeledRecord, key: str):
    return record.labels.get(key)


def entity_value(record: LabeledRecord, key: str):
    return dict(record.labels.get("entities") or {}).get(key)


def explicit_entity_spans(record: LabeledRecord) -> list[dict]:
    return list(record.labels.get("entity_spans") or [])


def infer_entity_spans(record: LabeledRecord) -> list[dict]:
    text = feature_text(record.features)
    lowered = text.lower()
    spans: list[dict] = []

    for field, label in STRING_ENTITY_FIELDS.items():
        value = entity_value(record, field)
        if value in {None, ""}:
            continue
        candidate = str(value)
        start = lowered.find(candidate.lower())
        if start < 0:
            continue
        end = start + len(candidate)
        spans.append(
            {
                "label": label,
                "text": text[start:end],
                "start": start,
                "end": end,
                "source": "weak_alignment",
            }
        )
    return spans


def resolved_entity_spans(record: LabeledRecord) -> list[dict]:
    explicit = explicit_entity_spans(record)
    if explicit:
        return explicit
    return infer_entity_spans(record)
