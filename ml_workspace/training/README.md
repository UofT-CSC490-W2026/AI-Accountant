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
