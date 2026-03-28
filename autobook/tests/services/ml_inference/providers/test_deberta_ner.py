"""Tests for services/ml_inference/providers/deberta_ner.py.

torch and transformers are always mocked. _collect_spans is pure Python — tested directly.
"""
import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub torch and transformers before importing the module under test
# ---------------------------------------------------------------------------

_mock_torch = MagicMock()
_mock_transformers = ModuleType("transformers")
_mock_transformers.AutoModelForTokenClassification = MagicMock()
_mock_transformers.AutoTokenizer = MagicMock()

sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("transformers", _mock_transformers)

from services.ml_inference.providers.base import ModelNotReadyError
from services.ml_inference.providers.deberta_ner import DebertaEntityExtractor
from services.ml_inference.schemas import EntityExtractionResult


class TestIsReady:
    def test_no_path_returns_false(self):
        ext = DebertaEntityExtractor(model_path=None)
        assert ext.is_ready is False

    def test_missing_tag_labels_returns_false(self, tmp_path):
        ext = DebertaEntityExtractor(model_path=str(tmp_path))
        assert ext.is_ready is False

    def test_with_tag_labels_returns_true(self, tmp_path):
        (tmp_path / "tag_labels.json").write_text('{"labels": ["O", "B-VENDOR"]}')
        ext = DebertaEntityExtractor(model_path=str(tmp_path))
        assert ext.is_ready is True


class TestRequireReady:
    def test_no_path_raises(self):
        ext = DebertaEntityExtractor(model_path=None)
        with pytest.raises(ModelNotReadyError, match="not configured"):
            ext._require_ready()

    def test_nonexistent_path_raises(self):
        ext = DebertaEntityExtractor(model_path="/nonexistent/path/abc123")
        with pytest.raises(ModelNotReadyError, match="does not exist"):
            ext._require_ready()

    def test_missing_tag_labels_raises(self, tmp_path):
        ext = DebertaEntityExtractor(model_path=str(tmp_path))
        with pytest.raises(ModelNotReadyError, match="tag_labels.json"):
            ext._require_ready()

    def test_valid_path_returns(self, tmp_path):
        (tmp_path / "tag_labels.json").write_text('{"labels": ["O"]}')
        ext = DebertaEntityExtractor(model_path=str(tmp_path))
        result = ext._require_ready()
        assert result == tmp_path


class TestCollectSpans:
    """_collect_spans is pure Python BIO parsing — no mocks needed."""

    def test_simple_b_tag(self):
        text = "Paid to Acme Corp"
        offsets = [(0, 4), (5, 7), (8, 12), (13, 17)]
        labels = ["O", "O", "B-VENDOR", "I-VENDOR"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert "VENDOR" in result
        assert result["VENDOR"] == ["Acme Corp"]

    def test_multiple_entities(self):
        text = "Bought laptop from BestBuy"
        offsets = [(0, 6), (7, 13), (14, 18), (19, 26)]
        labels = ["O", "B-ASSET_NAME", "O", "B-VENDOR"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result["ASSET_NAME"] == ["laptop"]
        assert result["VENDOR"] == ["BestBuy"]

    def test_all_o_tags_returns_empty(self):
        text = "hello world"
        offsets = [(0, 5), (6, 11)]
        labels = ["O", "O"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result == {}

    def test_consecutive_b_tags_create_separate_spans(self):
        text = "John Jane"
        offsets = [(0, 4), (5, 9)]
        labels = ["B-VENDOR", "B-VENDOR"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result["VENDOR"] == ["John", "Jane"]

    def test_skip_zero_length_offsets(self):
        text = "Acme Corp"
        offsets = [(0, 0), (0, 4), (5, 9)]
        labels = ["O", "B-VENDOR", "I-VENDOR"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result["VENDOR"] == ["Acme Corp"]

    def test_i_tag_without_matching_b_starts_new_span(self):
        text = "Acme Corp Ltd"
        offsets = [(0, 4), (5, 9), (10, 13)]
        labels = ["I-VENDOR", "I-VENDOR", "I-VENDOR"]

        # First I-VENDOR starts the span since there's no prior entity
        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert "VENDOR" in result
        assert len(result["VENDOR"]) == 1
        assert result["VENDOR"][0] == "Acme Corp Ltd"

    def test_different_entity_after_i_flushes(self):
        text = "Acme laptop"
        offsets = [(0, 4), (5, 11)]
        labels = ["B-VENDOR", "B-ASSET_NAME"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result["VENDOR"] == ["Acme"]
        assert result["ASSET_NAME"] == ["laptop"]

    def test_b_tag_for_different_entity_flushes_previous(self):
        text = "bought from Acme on 2026-01-01"
        offsets = [(0, 6), (7, 11), (12, 16), (17, 19), (20, 30)]
        labels = ["O", "O", "B-VENDOR", "O", "B-MENTIONED_DATE"]

        result = DebertaEntityExtractor._collect_spans(text, offsets, labels)

        assert result["VENDOR"] == ["Acme"]
        assert result["MENTIONED_DATE"] == ["2026-01-01"]


class TestExtractEntities:
    def test_extract_entities_full_flow(self, tmp_path):
        """Test extract_entities with a fully mocked pipeline."""
        # Write tag_labels.json
        labels = ["O", "B-VENDOR", "I-VENDOR", "B-ASSET_NAME"]
        (tmp_path / "tag_labels.json").write_text(json.dumps({"labels": labels}))

        ext = DebertaEntityExtractor(model_path=str(tmp_path))

        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        # Tokenizer returns encoded with offset_mapping
        mock_offset_mapping = MagicMock()
        mock_offset_mapping.__getitem__ = MagicMock(return_value=MagicMock(
            tolist=MagicMock(return_value=[(0, 0), (0, 6), (7, 13), (14, 18)])
        ))

        encoded = MagicMock()
        encoded.pop.return_value = mock_offset_mapping
        encoded.__contains__ = MagicMock(return_value=True)
        mock_tokenizer.return_value = encoded

        # Model returns logits
        mock_logits = MagicMock()
        mock_logits.__getitem__ = MagicMock(return_value=mock_logits)
        mock_model.return_value.logits = [mock_logits]

        # argmax returns prediction_ids: O, B-VENDOR, I-VENDOR, B-ASSET_NAME => [0, 1, 2, 3]
        mock_torch.argmax.return_value = MagicMock(tolist=MagicMock(return_value=[0, 1, 2, 3]))

        ext._pipeline = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
            "labels": labels,
        }

        message = {
            "amount_mentions": [{"value": 500}],
            "transaction_date": "2026-03-22",
        }
        text = "Bought laptop from Acme"

        result = ext.extract_entities(message, text)

        assert isinstance(result, EntityExtractionResult)
        assert result.amount == 500.0
        assert result.entities["amount"] == 500.0
        assert result.entities["date"] == "2026-03-22"
        assert result.entities["source_text"] == text

    def test_extract_entities_no_amount(self, tmp_path):
        """When no amount_mentions, amount is None."""
        labels = ["O", "B-VENDOR"]
        (tmp_path / "tag_labels.json").write_text(json.dumps({"labels": labels}))

        ext = DebertaEntityExtractor(model_path=str(tmp_path))

        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        mock_offset_mapping = MagicMock()
        mock_offset_mapping.__getitem__ = MagicMock(return_value=MagicMock(
            tolist=MagicMock(return_value=[(0, 0), (0, 4)])
        ))

        encoded = MagicMock()
        encoded.pop.return_value = mock_offset_mapping
        mock_tokenizer.return_value = encoded

        mock_logits = MagicMock()
        mock_model.return_value.logits = [mock_logits]
        mock_torch.argmax.return_value = MagicMock(tolist=MagicMock(return_value=[0, 1]))

        ext._pipeline = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
            "labels": labels,
        }

        message = {}
        result = ext.extract_entities(message, "Acme")

        assert result.amount is None

    def test_pipeline_caching(self, tmp_path):
        """Second call to _load returns cached pipeline."""
        labels = ["O"]
        (tmp_path / "tag_labels.json").write_text(json.dumps({"labels": labels}))

        ext = DebertaEntityExtractor(model_path=str(tmp_path))
        mock_pipeline = {
            "torch": MagicMock(),
            "tokenizer": MagicMock(),
            "model": MagicMock(),
            "labels": labels,
        }
        ext._pipeline = mock_pipeline

        result = ext._load()
        assert result is mock_pipeline

    def test_quantity_extraction(self, tmp_path):
        """When quantity_mentions has one entry, quantity is extracted."""
        labels = ["O"]
        (tmp_path / "tag_labels.json").write_text(json.dumps({"labels": labels}))

        ext = DebertaEntityExtractor(model_path=str(tmp_path))

        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        mock_offset_mapping = MagicMock()
        mock_offset_mapping.__getitem__ = MagicMock(return_value=MagicMock(
            tolist=MagicMock(return_value=[(0, 0), (0, 4)])
        ))
        encoded = MagicMock()
        encoded.pop.return_value = mock_offset_mapping
        mock_tokenizer.return_value = encoded

        mock_logits = MagicMock()
        mock_model.return_value.logits = [mock_logits]
        mock_torch.argmax.return_value = MagicMock(tolist=MagicMock(return_value=[0, 0]))

        ext._pipeline = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
            "labels": labels,
        }

        message = {"quantity_mentions": [{"value": 5}]}
        result = ext.extract_entities(message, "test")

        assert result.entities["quantity"] == 5


class TestLoad:
    """Test _load method (lines 35-53) with mocked torch/transformers."""

    def test_load_creates_pipeline(self, tmp_path):
        model_dir = tmp_path / "ner"
        model_dir.mkdir()
        (model_dir / "tag_labels.json").write_text(json.dumps({"labels": ["O", "B-VENDOR", "I-VENDOR"]}))

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        transformers_mod = sys.modules["transformers"]
        transformers_mod.AutoModelForTokenClassification = MagicMock(from_pretrained=MagicMock(return_value=mock_model))
        transformers_mod.AutoTokenizer = MagicMock(from_pretrained=MagicMock(return_value=mock_tokenizer))

        ext = DebertaEntityExtractor(str(model_dir))
        ext._pipeline = None  # force fresh load
        pipeline = ext._load()

        assert pipeline["labels"] == ["O", "B-VENDOR", "I-VENDOR"]
        assert pipeline["model"] is mock_model
        assert pipeline["tokenizer"] is mock_tokenizer
        mock_model.eval.assert_called_once()

    def test_load_caches_pipeline(self, tmp_path):
        model_dir = tmp_path / "ner"
        model_dir.mkdir()
        (model_dir / "tag_labels.json").write_text(json.dumps({"labels": ["O"]}))

        transformers_mod = sys.modules["transformers"]
        transformers_mod.AutoModelForTokenClassification = MagicMock(from_pretrained=MagicMock(return_value=MagicMock()))
        transformers_mod.AutoTokenizer = MagicMock(from_pretrained=MagicMock(return_value=MagicMock()))

        ext = DebertaEntityExtractor(str(model_dir))
        ext._pipeline = None
        p1 = ext._load()
        p2 = ext._load()
        assert p1 is p2


class TestExtractEntitiesEdgeCases:
    """Cover entity-setting branches: transfer_destination (128), mentioned_date (130), party_mentions (135)."""

    def _make_extractor_with_spans(self, spans: dict):
        """Create extractor with pre-injected pipeline returning specific spans."""
        mock_torch = MagicMock()
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()
        labels = ["O", "B-VENDOR", "B-TRANSFER_DESTINATION", "B-MENTIONED_DATE"]

        # Build predictions that produce the desired spans
        offsets = [[0, 5]]
        pred_ids = [0]  # just O — we'll override _collect_spans
        encoded = {"offset_mapping": mock_torch.tensor([[offsets]])}
        mock_tokenizer.return_value = encoded
        mock_model.return_value = MagicMock(logits=mock_torch.tensor([[[0]]]))
        mock_torch.argmax.return_value = MagicMock(tolist=lambda: pred_ids)
        mock_torch.tensor = MagicMock(return_value=MagicMock(__getitem__=lambda s, i: MagicMock(tolist=lambda: offsets)))

        ext = DebertaEntityExtractor()
        ext._pipeline = {
            "torch": mock_torch,
            "tokenizer": mock_tokenizer,
            "model": mock_model,
            "labels": labels,
        }
        return ext

    def test_transfer_destination_set(self):
        ext = self._make_ext_with_span_patch({"TRANSFER_DESTINATION": ["Savings Account"]})
        with patch.object(DebertaEntityExtractor, "_collect_spans", return_value={"TRANSFER_DESTINATION": ["Savings Account"]}):
            result = ext.extract_entities({}, "transfer to Savings Account")
        assert result.entities.get("transfer_destination") == "Savings Account"

    def _make_ext_with_span_patch(self, spans):
        mock_torch = MagicMock()
        mock_torch.argmax.return_value = MagicMock(tolist=lambda: [0])
        offsets_tensor = MagicMock()
        offsets_tensor.__getitem__ = lambda s, i: MagicMock(tolist=lambda: [[0, 1]])
        encoded = MagicMock()
        encoded.pop.return_value = offsets_tensor
        mock_tokenizer = MagicMock(return_value=encoded)
        mock_model = MagicMock()
        mock_model.return_value = MagicMock(logits=MagicMock(__getitem__=lambda s, i: MagicMock()))
        ext = DebertaEntityExtractor()
        ext._pipeline = {"torch": mock_torch, "tokenizer": mock_tokenizer, "model": mock_model, "labels": ["O"]}
        return ext

    def test_mentioned_date_set(self):
        ext = self._make_ext_with_span_patch({"MENTIONED_DATE": ["2026-03-15"]})
        with patch.object(DebertaEntityExtractor, "_collect_spans", return_value={"MENTIONED_DATE": ["2026-03-15"]}):
            result = ext.extract_entities({}, "due 2026-03-15")
        assert result.entities.get("mentioned_date") == "2026-03-15"

    def test_party_mentions_set(self):
        ext = self._make_ext_with_span_patch({})
        with patch.object(DebertaEntityExtractor, "_collect_spans", return_value={}):
            result = ext.extract_entities({"party_mentions": [{"value": "Apple"}]}, "from Apple")
        assert result.entities.get("party_mentions") == [{"value": "Apple"}]
