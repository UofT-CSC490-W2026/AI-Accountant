from __future__ import annotations

import json
from pathlib import Path

from services.ml_inference.providers.base import EntityExtractor, ModelNotReadyError
from services.ml_inference.schemas import EntityExtractionResult


class DebertaEntityExtractor(EntityExtractor):
    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._pipeline = None

    @property
    def is_ready(self) -> bool:
        if not self.model_path:
            return False
        root = Path(self.model_path)
        return root.exists() and (root / "tag_labels.json").exists()

    def _require_ready(self) -> Path:
        if not self.model_path:
            raise ModelNotReadyError("DeBERTa entity model path is not configured.")
        root = Path(self.model_path)
        if not root.exists():
            raise ModelNotReadyError(f"DeBERTa entity model path does not exist: {root}")
        if not (root / "tag_labels.json").exists():
            raise ModelNotReadyError(f"Missing tag_labels.json in entity model artifact: {root}")
        return root

    def _load(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
        except Exception as exc:
            raise ModelNotReadyError("transformers/torch are not available for DeBERTa entity loading.") from exc

        root = self._require_ready()
        tokenizer = AutoTokenizer.from_pretrained(root)
        model = AutoModelForTokenClassification.from_pretrained(root)
        model.eval()
        with (root / "tag_labels.json").open("r", encoding="utf-8") as handle:
            labels_payload = json.load(handle)
        self._pipeline = {
            "torch": torch,
            "tokenizer": tokenizer,
            "model": model,
            "labels": list(labels_payload.get("labels") or []),
        }
        return self._pipeline

    @staticmethod
    def _collect_spans(text: str, offsets, predicted_labels: list[str]) -> dict[str, list[str]]:
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

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        pipeline = self._load()
        torch = pipeline["torch"]
        tokenizer = pipeline["tokenizer"]
        model = pipeline["model"]
        labels = pipeline["labels"]

        encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=256, return_offsets_mapping=True)
        offsets = encoded.pop("offset_mapping")[0].tolist()
        with torch.no_grad():
            logits = model(**encoded).logits[0]
            prediction_ids = torch.argmax(logits, dim=-1).tolist()
        predicted_labels = [labels[index] for index in prediction_ids]
        spans = self._collect_spans(text, offsets, predicted_labels)

        amount = None
        amount_mentions = list(message.get("amount_mentions") or [])
        if len(amount_mentions) == 1 and amount_mentions[0].get("value") is not None:
            amount = float(amount_mentions[0]["value"])

        quantity = None
        quantity_mentions = list(message.get("quantity_mentions") or [])
        if len(quantity_mentions) == 1 and quantity_mentions[0].get("value") is not None:
            quantity = int(quantity_mentions[0]["value"])

        vendor = (spans.get("VENDOR") or [None])[0]
        asset_name = (spans.get("ASSET_NAME") or [None])[0]
        transfer_destination = (spans.get("TRANSFER_DESTINATION") or [None])[0]
        mentioned_date = (spans.get("MENTIONED_DATE") or [None])[0]

        entities = dict(message.get("entities") or {})
        if amount is not None:
            entities["amount"] = amount
        if vendor:
            entities["vendor"] = vendor
        if asset_name:
            entities["asset_name"] = asset_name.lower()
        if quantity is not None:
            entities["quantity"] = quantity
        if transfer_destination:
            entities["transfer_destination"] = transfer_destination
        if mentioned_date:
            entities["mentioned_date"] = mentioned_date
        if amount_mentions:
            entities.setdefault("amount_mentions", amount_mentions)
        party_mentions = list(message.get("party_mentions") or [])
        if party_mentions:
            entities.setdefault("party_mentions", party_mentions)
        if quantity_mentions:
            entities.setdefault("quantity_mentions", quantity_mentions)
        entities.setdefault("source_text", text)
        entities.setdefault("date", str(message.get("transaction_date") or ""))

        return EntityExtractionResult(
            amount=amount,
            vendor=vendor,
            asset_name=asset_name.lower() if asset_name else None,
            entities=entities,
        )
