# Training

Put training code, experiment configs, and notes here.

Recommended structure:
- `classifier/`
- `entity_extractor/`
- `configs/`
- `runs/`

Suggested training split:
- sequence classifier for `intent_label`, `bank_category`, `cca_class_match`
- token or span extractor for entities

Keep exported artifacts out of this folder. Save them into `../artifacts/`.

## First Script

`train_classifier.py` is the first entrypoint in this workspace.

Right now it is intentionally a smoke trainer:
- loads the placeholder dataset
- validates record structure
- extracts label maps
- writes artifact metadata into `../artifacts/smoke_classifier/`

Run it with:

```powershell
python ml_workspace/training/train_classifier.py
```

## Real Training Scaffold

The DeBERTa training scaffold now exists in:
- `train_deberta_sequence.py`
- `train_deberta_ner.py`
- `dataset.py`
- `hf_dataset.py`
- `shared/infra.py`
- `runners/`
- `configs/deberta_smoke.yaml`

Local training commands:

```powershell
python ml_workspace/training/train_deberta_sequence.py --base-model microsoft/deberta-v3-small
python ml_workspace/training/train_deberta_ner.py --base-model microsoft/deberta-v3-small
```

Modal training command:

```powershell
modal run ml_workspace/training/main.py --config ml_workspace/training/configs/deberta_smoke.yaml
```
