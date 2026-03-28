# Dataset Specification

The labeled dataset mirrors the ML inference contract already used by `autobook`.

Each record is split into:

- `features`: the input available to the ML layer after normalization
- `labels`: the gold output the ML layer should predict

## Record Shape

```json
{
  "record_id": "train-001",
  "features": {
    "input_text": "Bought a laptop from Apple for $2400",
    "normalized_text": "bought a laptop from apple for $2400",
    "source": "manual_text",
    "currency": "CAD",
    "transaction_date": "2026-03-22",
    "amount_mentions": [
      { "text": "$2400", "value": 2400.0 }
    ],
    "date_mentions": [],
    "party_mentions": [
      { "text": "Apple", "value": "Apple" }
    ],
    "quantity_mentions": [
      { "text": "1 laptop", "value": 1, "unit": "laptop" }
    ]
  },
  "labels": {
    "intent_label": "asset_purchase",
    "bank_category": "equipment",
    "cca_class_match": "class_50",
    "entities": {
      "amount": 2400.0,
      "vendor": "Apple",
      "asset_name": "laptop",
      "quantity": 1,
      "mentioned_date": null,
      "transfer_destination": null
    },
    "entity_spans": [
      { "label": "VENDOR", "text": "Apple", "start": 21, "end": 26 },
      { "label": "ASSET_NAME", "text": "laptop", "start": 9, "end": 15 }
    ]
  }
}
```

## Why This Structure

- `features` maps to the ML layer input contract
- `labels` maps to the ML layer output contract
- this keeps training data aligned with runtime inference expectations

## Feature Fields

Core required fields:
- `input_text`
- `source`
- `currency`
- `transaction_date`

Optional normalizer-derived fields:
- `normalized_text`
- `amount_mentions`
- `date_mentions`
- `party_mentions`
- `quantity_mentions`
- `amount`
- `counterparty`
- `normalized_description`

## Label Fields

Required:
- `intent_label`
- `bank_category`
- `cca_class_match`
- `entities`

Optional but recommended for token-classification entity training:
- `entity_spans`

Entity fields currently expected:
- `amount`
- `vendor`
- `asset_name`
- `quantity`
- `mentioned_date`
- `transfer_destination`

## Non-Goals

Do not include downstream runtime outputs as labels:
- `precedent_match`
- `proposed_entry`
- journal lines
- clarification status
- posting status

Those belong to later pipeline stages, not the ML layer.

## Runtime Mapping

The runtime ML service still consumes a flat message dict.

Training records stay nested as `features` + `labels`, and the adapter in:
- `ml_workspace/training/dataset.py`

is responsible for flattening `features` into runtime-style input when needed.

## Annotation Rules

Use [annotation_guidelines.md](C:/Users/rober/OneDrive/Desktop/study_file/Third_year_winter/CSC490/AI-Accountant/ml_workspace/data/schemas/annotation_guidelines.md) when creating or reviewing labels.
