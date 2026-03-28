from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED_TOP_LEVEL_FIELDS = {
    "record_id",
    "features",
    "labels",
}

REQUIRED_FEATURE_FIELDS = {
    "input_text",
    "source",
    "currency",
    "transaction_date",
}

REQUIRED_LABEL_FIELDS = {
    "intent_label",
    "bank_category",
    "cca_class_match",
    "entities",
}


def has_signal(value) -> bool:
    return value not in (None, "", [], {})


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} contains invalid JSON") from exc
            records.append(payload)
    return records


def validate_record(record: dict, *, path: Path, index: int) -> None:
    missing_top_level = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(record))
    if missing_top_level:
        raise ValueError(f"{path} record {index} is missing top-level fields: {missing_top_level}")

    features = record.get("features") or {}
    missing_feature_fields = sorted(REQUIRED_FEATURE_FIELDS - set(features))
    if missing_feature_fields:
        raise ValueError(f"{path} record {index} is missing feature fields: {missing_feature_fields}")

    labels = record.get("labels") or {}
    missing_label_fields = sorted(REQUIRED_LABEL_FIELDS - set(labels))
    if missing_label_fields:
        raise ValueError(f"{path} record {index} is missing label fields: {missing_label_fields}")

    if not isinstance(features, dict):
        raise ValueError(f"{path} record {index} has non-object features")
    if not isinstance(labels.get("entities"), dict):
        raise ValueError(f"{path} record {index} has non-object labels.entities")


def summarize(records: list[dict]) -> dict:
    intent_counts = Counter()
    bank_category_counts = Counter()
    cca_counts = Counter()
    entity_coverage = Counter()
    sources = Counter()

    for record in records:
        features = record["features"]
        labels = record["labels"]
        intent_counts.update([labels.get("intent_label") or "__null__"])
        bank_category_counts.update([labels.get("bank_category") or "__null__"])
        cca_counts.update([labels.get("cca_class_match") or "__null__"])
        sources.update([features.get("source") or "__null__"])

        for key, value in (labels.get("entities") or {}).items():
            if has_signal(value):
                entity_coverage.update([key])

    return {
        "record_count": len(records),
        "sources": dict(sorted(sources.items())),
        "intent_counts": dict(sorted(intent_counts.items())),
        "bank_category_counts": dict(sorted(bank_category_counts.items())),
        "cca_class_counts": dict(sorted(cca_counts.items())),
        "entity_coverage": dict(sorted(entity_coverage.items())),
    }


def build_label_maps(train_records: list[dict], validation_records: list[dict]) -> dict:
    combined = train_records + validation_records
    intents = sorted(
        {
            record["labels"].get("intent_label")
            for record in combined
            if record["labels"].get("intent_label") is not None
        }
    )
    bank_categories = sorted(
        {
            record["labels"].get("bank_category")
            for record in combined
            if record["labels"].get("bank_category") is not None
        }
    )
    cca_classes = sorted(
        {
            record["labels"].get("cca_class_match")
            for record in combined
            if record["labels"].get("cca_class_match") is not None
        }
    )
    entity_fields = sorted(
        {
            key
            for record in combined
            for key, value in (record["labels"].get("entities") or {}).items()
            if has_signal(value)
        }
    )

    return {
        "intent_label": intents,
        "bank_category": bank_categories,
        "cca_class_match": cca_classes,
        "entity_fields": entity_fields,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    workspace_root = Path(__file__).resolve().parents[1]
    default_train = workspace_root / "data" / "processed" / "train.jsonl"
    default_validation = workspace_root / "data" / "processed" / "validation.jsonl"
    default_output = workspace_root / "artifacts" / "smoke_classifier"

    parser = argparse.ArgumentParser(
        description="Validate the placeholder ML dataset and emit smoke artifact metadata."
    )
    parser.add_argument("--train-path", type=Path, default=default_train)
    parser.add_argument("--validation-path", type=Path, default=default_validation)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_records = load_jsonl(args.train_path)
    validation_records = load_jsonl(args.validation_path)

    for index, record in enumerate(train_records, start=1):
        validate_record(record, path=args.train_path, index=index)
    for index, record in enumerate(validation_records, start=1):
        validate_record(record, path=args.validation_path, index=index)

    label_maps = build_label_maps(train_records, validation_records)
    summary = {
        "mode": "smoke_placeholder",
        "train": summarize(train_records),
        "validation": summarize(validation_records),
        "label_maps": label_maps,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "label_maps.json", label_maps)
    write_json(args.output_dir / "run_summary.json", summary)

    print(f"Wrote smoke artifacts to {args.output_dir}")


if __name__ == "__main__":
    main()
