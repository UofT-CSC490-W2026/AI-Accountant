from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml_workspace.training.dataset import flattened_runtime_message, load_records
from ml_workspace.training.hf_dataset import build_classification_examples

CLASSIFICATION_TASKS = ("intent_label",)
ENTITY_FIELDS = ("vendor", "asset_name", "transfer_destination", "mentioned_date")


@dataclass(frozen=True)
class EvaluationConfig:
    classifier_dir: Path
    entity_dir: Path
    test_path: Path
    output_dir: Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _accuracy(predictions: list[str], references: list[str]) -> float:
    if not references:
        return 0.0
    correct = sum(1 for pred, ref in zip(predictions, references) if pred == ref)
    return correct / len(references)


def _macro_f1(predictions: list[str], references: list[str]) -> float:
    labels = sorted(set(predictions) | set(references))
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        tp = sum(1 for pred, ref in zip(predictions, references) if pred == label and ref == label)
        fp = sum(1 for pred, ref in zip(predictions, references) if pred == label and ref != label)
        fn = sum(1 for pred, ref in zip(predictions, references) if pred != label and ref == label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision == 0.0 and recall == 0.0:
            scores.append(0.0)
        else:
            scores.append((2 * precision * recall) / (precision + recall))
    return sum(scores) / len(scores)


def _load_sequence_pipeline(task_dir: Path):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(task_dir)
    model = AutoModelForSequenceClassification.from_pretrained(task_dir)
    model.eval()
    return tokenizer, model


def _predict_sequence_label(tokenizer, model, text: str) -> str:
    import torch

    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        logits = model(**encoded).logits
        index = int(torch.argmax(logits, dim=-1)[0].item())
    label = model.config.id2label.get(index)
    return "__null__" if label in {None, "__null__"} else str(label)


def evaluate_classifier_artifacts(classifier_dir: Path, test_records: list) -> dict:
    summary: dict[str, dict] = {}
    for task_name in CLASSIFICATION_TASKS:
        task_dir = classifier_dir / task_name
        tokenizer, model = _load_sequence_pipeline(task_dir)
        examples = build_classification_examples(test_records, task_name)
        predictions = [_predict_sequence_label(tokenizer, model, example["text"]) for example in examples]
        references = [str(example["label"]) for example in examples]
        summary[task_name] = {
            "accuracy": _accuracy(predictions, references),
            "macro_f1": _macro_f1(predictions, references),
            "count": len(examples),
        }
    return summary


def _load_entity_pipeline(entity_dir: Path):
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(entity_dir)
    model = AutoModelForTokenClassification.from_pretrained(entity_dir)
    model.eval()
    with (entity_dir / "tag_labels.json").open("r", encoding="utf-8") as handle:
        labels_payload = json.load(handle)
    return torch, tokenizer, model, list(labels_payload.get("labels") or [])


def _collect_spans(text: str, offsets: list[list[int]], predicted_labels: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    current_label = None
    current_start = None
    current_end = None

    def flush():
        nonlocal current_label, current_start, current_end
        if current_label is None or current_start is None or current_end is None:
            return
        grouped.setdefault(current_label, []).append(text[current_start:current_end].strip())
        current_label = None
        current_start = None
        current_end = None

    for (start, end), predicted in zip(offsets, predicted_labels):
        if start == end:
            continue
        if predicted == "O":
            flush()
            continue
        prefix, entity = predicted.split("-", 1)
        if prefix == "B" or entity != current_label:
            flush()
            current_label = entity
            current_start = start
            current_end = end
        else:
            current_end = end
    flush()
    return grouped


def _predict_entity_values(torch, tokenizer, model, labels: list[str], message: dict, text: str) -> dict[str, str | None]:
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=256, return_offsets_mapping=True)
    offsets = encoded.pop("offset_mapping")[0].tolist()
    with torch.no_grad():
        logits = model(**encoded).logits[0]
        prediction_ids = torch.argmax(logits, dim=-1).tolist()
    predicted_labels = [labels[index] for index in prediction_ids]
    spans = _collect_spans(text, offsets, predicted_labels)
    return {
        "vendor": (spans.get("VENDOR") or [None])[0],
        "asset_name": ((spans.get("ASSET_NAME") or [None])[0] or None),
        "transfer_destination": (spans.get("TRANSFER_DESTINATION") or [None])[0],
        "mentioned_date": (spans.get("MENTIONED_DATE") or [None])[0],
    }


def evaluate_entity_artifact(entity_dir: Path, test_records: list) -> dict:
    torch, tokenizer, model, labels = _load_entity_pipeline(entity_dir)
    per_field: dict[str, dict] = {}
    for field_name in ENTITY_FIELDS:
        predictions: list[str] = []
        references: list[str] = []
        for record in test_records:
            message = flattened_runtime_message(record)
            predicted = _predict_entity_values(torch, tokenizer, model, labels, message, str(record.features.get("input_text") or ""))
            gold = dict(record.labels.get("entities") or {})
            predicted_value = predicted.get(field_name)
            gold_value = gold.get(field_name)
            predictions.append("__null__" if predicted_value in {None, ""} else str(predicted_value).lower())
            references.append("__null__" if gold_value in {None, ""} else str(gold_value).lower())
        per_field[field_name] = {
            "accuracy": _accuracy(predictions, references),
            "macro_f1": _macro_f1(predictions, references),
            "count": len(references),
        }
    exact_match = []
    for record in test_records:
        message = flattened_runtime_message(record)
        predicted = _predict_entity_values(torch, tokenizer, model, labels, message, str(record.features.get("input_text") or ""))
        gold = dict(record.labels.get("entities") or {})
        exact_match.append(
            all(
                ("__null__" if predicted.get(field) in {None, ""} else str(predicted.get(field)).lower())
                == ("__null__" if gold.get(field) in {None, ""} else str(gold.get(field)).lower())
                for field in ENTITY_FIELDS
            )
        )
    return {
        "per_field": per_field,
        "exact_match_accuracy": (sum(1 for item in exact_match if item) / len(exact_match)) if exact_match else 0.0,
        "count": len(test_records),
    }


def evaluate_saved_models(config: EvaluationConfig) -> dict:
    test_records = load_records(config.test_path)
    if not test_records:
        raise ValueError(f"No test records found in {config.test_path}")
    classifier_summary = evaluate_classifier_artifacts(config.classifier_dir, test_records)
    entity_summary = evaluate_entity_artifact(config.entity_dir, test_records)
    summary = {
        "test_path": str(config.test_path),
        "test_records": len(test_records),
        "classifier": classifier_summary,
        "entity": entity_summary,
    }
    _write_json(config.output_dir / "test_metrics.json", summary)
    return summary


def _parse_args() -> EvaluationConfig:
    workspace_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Evaluate saved Autobook ML artifacts on a held-out test set.")
    parser.add_argument("--classifier-dir", type=Path, required=True)
    parser.add_argument("--entity-dir", type=Path, required=True)
    parser.add_argument("--test-path", type=Path, default=workspace_root / "data" / "processed" / "test.jsonl")
    parser.add_argument("--output-dir", type=Path, default=workspace_root / "artifacts" / "evaluation")
    args = parser.parse_args()
    return EvaluationConfig(
        classifier_dir=args.classifier_dir,
        entity_dir=args.entity_dir,
        test_path=args.test_path,
        output_dir=args.output_dir,
    )


def main() -> None:
    config = _parse_args()
    summary = evaluate_saved_models(config)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
