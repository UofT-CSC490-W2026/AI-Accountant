"""Tests for services/ml_inference/providers/deberta_classifier.py.

torch and transformers are always mocked since they are not installed in the test env.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub torch and transformers before importing the module under test
# ---------------------------------------------------------------------------

_mock_torch = MagicMock()
_mock_transformers = ModuleType("transformers")
_mock_transformers.AutoModelForSequenceClassification = MagicMock()
_mock_transformers.AutoTokenizer = MagicMock()

sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("transformers", _mock_transformers)

from services.ml_inference.providers.base import ModelNotReadyError
from services.ml_inference.providers.deberta_classifier import (
    INTENT_LABELS,
    DebertaSequenceClassifier,
)
from services.ml_inference.schemas import ClassificationResult


class TestIsReady:
    def test_no_path_returns_false(self):
        clf = DebertaSequenceClassifier(model_path=None)
        assert clf.is_ready is False

    def test_missing_intent_dir_returns_false(self, tmp_path):
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))
        assert clf.is_ready is False

    def test_with_intent_dir_returns_true(self, tmp_path):
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))
        assert clf.is_ready is True


class TestRequireReady:
    def test_no_path_raises(self):
        clf = DebertaSequenceClassifier(model_path=None)
        with pytest.raises(ModelNotReadyError, match="not configured"):
            clf._require_ready()

    def test_nonexistent_path_raises(self):
        clf = DebertaSequenceClassifier(model_path="/nonexistent/path/abc123")
        with pytest.raises(ModelNotReadyError, match="does not exist"):
            clf._require_ready()

    def test_existing_path_returns_path(self, tmp_path):
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))
        result = clf._require_ready()
        assert result == tmp_path


class TestTaskDir:
    def test_missing_task_dir_raises(self, tmp_path):
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))
        with pytest.raises(ModelNotReadyError, match="Missing trained classifier"):
            clf._task_dir("intent_label")

    def test_existing_task_dir_returns_path(self, tmp_path):
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))
        result = clf._task_dir("intent_label")
        assert result == tmp_path / "intent_label"


class TestPredictLabel:
    def test_predict_label_flow(self, tmp_path):
        """Full _predict_label flow with mocked torch and transformers."""
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))

        # Set up mock torch
        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        # Tokenizer returns encoded input
        encoded = {"input_ids": MagicMock(), "attention_mask": MagicMock()}
        mock_tokenizer.return_value = encoded

        # Model returns logits
        mock_logits = MagicMock()
        mock_model.return_value.logits = mock_logits

        # softmax returns probabilities
        mock_probs = MagicMock()
        mock_probs.__getitem__ = MagicMock(return_value=mock_probs)
        mock_torch.softmax.return_value = mock_probs

        # argmax returns index 2
        mock_argmax = MagicMock()
        mock_argmax.item.return_value = 2
        mock_torch.argmax.return_value = mock_argmax

        # confidence
        mock_conf = MagicMock()
        mock_conf.item.return_value = 0.95
        mock_probs.__getitem__ = MagicMock(return_value=mock_conf)

        # Model config id2label
        mock_model.config.id2label = {0: "asset_purchase", 1: "rent_expense", 2: "bank_fee"}

        # Patch _load_pipeline to inject our mocks
        clf._pipelines["intent_label"] = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
        }

        result = clf._predict_label("intent_label", "test text")

        assert isinstance(result, ClassificationResult)
        mock_tokenizer.assert_called_once_with(
            "test text", return_tensors="pt", truncation=True, max_length=256
        )

    def test_predict_label_null_label_returns_none(self, tmp_path):
        """When id2label returns __null__, result label is None."""
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))

        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        encoded = {"input_ids": MagicMock()}
        mock_tokenizer.return_value = encoded
        mock_model.return_value.logits = MagicMock()

        mock_probs = MagicMock()
        mock_probs.__getitem__ = MagicMock(return_value=MagicMock(item=MagicMock(return_value=0.5)))
        mock_torch.softmax.return_value = [mock_probs]
        mock_torch.argmax.return_value = MagicMock(item=MagicMock(return_value=0))

        mock_model.config.id2label = {0: "__null__"}

        clf._pipelines["intent_label"] = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
        }

        result = clf._predict_label("intent_label", "some text")
        assert result.label is None


class TestPredictIntent:
    def test_predict_intent_formats_input(self, tmp_path):
        """predict_intent prepends 'source: ... text: ...' to the input."""
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))

        # Mock _predict_label directly
        clf._predict_label = MagicMock(return_value=ClassificationResult("bank_fee", 0.9))

        result = clf.predict_intent("payment $500", "bank_statement")

        clf._predict_label.assert_called_once_with(
            "intent_label", "source: bank_statement text: payment $500"
        )
        assert result.label == "bank_fee"
        assert result.confidence == 0.9


class TestHeuristicOnlyMethods:
    def test_predict_bank_category_raises(self):
        clf = DebertaSequenceClassifier()
        with pytest.raises(ModelNotReadyError, match="heuristic-only"):
            clf.predict_bank_category("text", "intent")

    def test_predict_cca_class_raises(self):
        clf = DebertaSequenceClassifier()
        with pytest.raises(ModelNotReadyError, match="heuristic-only"):
            clf.predict_cca_class("intent", "asset")


class TestLabels:
    def test_intent_labels_tuple(self):
        assert isinstance(INTENT_LABELS, tuple)
        assert "asset_purchase" in INTENT_LABELS
        assert "bank_fee" in INTENT_LABELS

    def test_pipeline_caching(self, tmp_path):
        """Second call to _load_pipeline returns cached pipeline."""
        (tmp_path / "intent_label").mkdir()
        clf = DebertaSequenceClassifier(model_path=str(tmp_path))

        mock_pipeline = {"torch": MagicMock(), "tokenizer": MagicMock(), "model": MagicMock()}
        clf._pipelines["intent_label"] = mock_pipeline

        result = clf._load_pipeline("intent_label")
        assert result is mock_pipeline
