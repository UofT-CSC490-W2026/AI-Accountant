# ML Workspace

This folder is the training and evaluation workspace for the Autobook ML layer.

It is intentionally outside `autobook/` so experiments, datasets, notebooks, and artifacts do not pollute the application runtime code.

## Purpose

Use this workspace for:
- labeled dataset preparation
- model training
- offline evaluation
- artifact packaging
- inference contract validation before wiring trained models into `autobook`

Do not put production backend code here unless it is clearly training- or evaluation-only.

## Layout

- `data/`
  - dataset schemas and labeled examples
- `training/`
  - training scripts, configs, and experiment notes
- `inference/`
  - artifact manifest templates and local inference wrappers
- `eval/`
  - evaluation plan and metric definitions
- `artifacts/`
  - exported checkpoints, tokenizers, label maps, calibration files
- `notebooks/`
  - optional exploration notebooks

## Planned Model Structure

The intended runtime shape matches the backend contract:

1. Sequence classifier
   - predicts `intent_label`
   - predicts `bank_category`
   - predicts `cca_class_match`
   - emits calibrated confidence

2. Entity extractor
   - extracts `vendor`
   - extracts `asset_name`
   - extracts `quantity`
   - extracts `mentioned_date`
   - extracts `transfer_destination`
   - can optionally emit mention spans

The runtime integration point already exists in:
- `autobook/backend/services/ml_inference/service.py`
- `autobook/backend/services/ml_inference/providers/`

## Workflow

1. Define and label training records in `data/`
2. Train classifier and entity extractor in `training/`
3. Export artifacts into `artifacts/`
4. Validate outputs against the backend contract
5. Point `autobook` config to exported model paths

## Integration Rule

The ML layer must not generate journal entries directly.

It should only output the structured fields consumed by the backend agent and rule engine:
- `intent_label`
- `entities`
- `bank_category`
- `cca_class_match`
- `confidence.ml`

Posting remains owned by the rule engine inside `autobook`.
