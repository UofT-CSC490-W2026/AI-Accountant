"""Tests for models — structure hash, extract_label, dataclasses."""
from services.precedent_v2.models import (
    Label, StructureLine, RatioLine,
    compute_structure_hash, extract_label,
)
from unittest.mock import MagicMock


class TestComputeStructureHash:
    def test_deterministic(self):
        s = {"lines": [{"account_code": "1000", "side": "debit"}]}
        assert compute_structure_hash(s) == compute_structure_hash(s)

    def test_different_structures_differ(self):
        s1 = {"lines": [{"account_code": "1000", "side": "debit"}]}
        s2 = {"lines": [{"account_code": "1000", "side": "credit"}]}
        assert compute_structure_hash(s1) != compute_structure_hash(s2)

    def test_key_order_irrelevant(self):
        s1 = {"lines": [{"account_code": "1000", "side": "debit"}]}
        s2 = {"lines": [{"side": "debit", "account_code": "1000"}]}
        assert compute_structure_hash(s1) == compute_structure_hash(s2)

    def test_is_sha256_hex(self):
        h = compute_structure_hash({"lines": []})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestExtractLabel:
    def test_extracts_correctly(self):
        entry = MagicMock()
        entry.structure = {"lines": [
            {"account_code": "5200", "side": "debit"},
            {"account_code": "1000", "side": "credit"},
        ]}
        entry.ratio = {"lines": [
            {"account_code": "5200", "ratio": 1.0},
            {"account_code": "1000", "ratio": 1.0},
        ]}
        entry.structure_hash = "abc"

        label = extract_label(entry)
        assert len(label.structure) == 2
        assert label.structure[0] == StructureLine("5200", "debit")
        assert label.ratio[1] == RatioLine("1000", 1.0)
        assert label.structure_hash == "abc"

    def test_empty_lines(self):
        entry = MagicMock()
        entry.structure = {"lines": []}
        entry.ratio = {"lines": []}
        entry.structure_hash = "empty"
        label = extract_label(entry)
        assert label.structure == ()
        assert label.ratio == ()


class TestDataclasses:
    def test_structure_line_frozen(self):
        sl = StructureLine("1000", "debit")
        assert sl.account_code == "1000"
        assert sl.side == "debit"

    def test_ratio_line_frozen(self):
        rl = RatioLine("1000", 0.75)
        assert rl.account_code == "1000"
        assert rl.ratio == 0.75

    def test_label_frozen(self):
        label = Label(
            structure=(StructureLine("1000", "debit"),),
            ratio=(RatioLine("1000", 1.0),),
            structure_hash="test",
        )
        assert label.structure_hash == "test"

    def test_labels_equality(self):
        l1 = Label(
            structure=(StructureLine("1000", "debit"),),
            ratio=(RatioLine("1000", 1.0),),
            structure_hash="same",
        )
        l2 = Label(
            structure=(StructureLine("1000", "debit"),),
            ratio=(RatioLine("1000", 1.0),),
            structure_hash="same",
        )
        assert l1 == l2
