# Inference

This folder is for local artifact manifests and thin inference wrappers used during model validation.

Runtime integration in the app is already prepared in:
- `autobook/backend/services/ml_inference/providers/deberta_classifier.py`
- `autobook/backend/services/ml_inference/providers/deberta_ner.py`
- `autobook/backend/services/ml_inference/service.py`

When trained artifacts exist, record their paths and metadata in a manifest here first.
