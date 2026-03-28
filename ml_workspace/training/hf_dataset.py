from __future__ import annotations

from dataclasses import dataclass

from ml_workspace.training.dataset import (
    LabeledRecord,
    classifier_text,
    entity_value,
    feature_text,
    label_value,
    null_safe_label,
    resolved_entity_spans,
)


def build_classification_examples(records: list[LabeledRecord], task_name: str) -> list[dict]:
    examples: list[dict] = []
    for record in records:
        label = null_safe_label(label_value(record, task_name))
        text = classifier_text(record)
        source = str(record.features.get("source") or "manual_text")
        if task_name == "intent_label":
            text = f"source: {source} text: {text}"
        examples.append(
            {
                "record_id": record.record_id,
                "text": text,
                "label": label,
            }
        )
    return examples


TOKEN_ENTITY_KEYS = {
    "VENDOR",
    "ASSET_NAME",
    "TRANSFER_DESTINATION",
    "MENTIONED_DATE",
}


@dataclass(frozen=True)
class TokenExample:
    record_id: str
    text: str
    spans: list[dict]


def build_token_examples(records: list[LabeledRecord]) -> list[TokenExample]:
    examples: list[TokenExample] = []
    for record in records:
        spans = [span for span in resolved_entity_spans(record) if span.get("label") in TOKEN_ENTITY_KEYS]
        if not spans:
            continue
        examples.append(
            TokenExample(
                record_id=record.record_id,
                text=feature_text(record.features),
                spans=sorted(spans, key=lambda item: (item["start"], item["end"])),
            )
        )
    return examples


def build_entity_value_examples(records: list[LabeledRecord]) -> list[dict]:
    examples: list[dict] = []
    for record in records:
        examples.append(
            {
                "record_id": record.record_id,
                "text": feature_text(record.features),
                "vendor": entity_value(record, "vendor"),
                "asset_name": entity_value(record, "asset_name"),
                "transfer_destination": entity_value(record, "transfer_destination"),
                "mentioned_date": entity_value(record, "mentioned_date"),
            }
        )
    return examples
