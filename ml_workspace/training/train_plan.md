# Training Plan

## Stage 1

Train a sequence classifier on:
- `intent_label`
- `bank_category`
- `cca_class_match`

Primary objective:
- high precision on auto-post-safe categories

## Stage 2

Train an entity extractor for:
- `vendor`
- `asset_name`
- `quantity`
- `mentioned_date`
- `transfer_destination`

## Stage 3

Calibrate confidence so backend routing can use:
- high confidence -> direct rule engine
- medium confidence -> reasoning fallback
- low confidence -> clarification

## Evaluation Priorities

Optimize for:
- low wrong-auto-post rate
- stable entity extraction on business/vendor names
- strong precision on transfer detection
