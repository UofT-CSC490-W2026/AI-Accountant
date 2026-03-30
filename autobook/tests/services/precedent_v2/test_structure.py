"""Tests for structure label extraction and consensus finding."""
from unittest.mock import MagicMock

from services.precedent_v2.models import (
    Label, PrecedentEntry, RatioLine, StructureLine,
    compute_structure_hash, extract_label,
)
from services.precedent_v2.structure import extract_labels, find_most_common


def _entry_with_structure(structure: dict, ratio: dict) -> MagicMock:
    e = MagicMock(spec=PrecedentEntry)
    e.structure = structure
    e.ratio = ratio
    e.structure_hash = compute_structure_hash(structure)
    return e


RENT_STRUCTURE = {"lines": [
    {"account_code": "5200", "side": "debit"},
    {"account_code": "1000", "side": "credit"},
]}
RENT_RATIO = {"lines": [
    {"account_code": "5200", "ratio": 1.0},
    {"account_code": "1000", "ratio": 1.0},
]}
EQUIP_STRUCTURE = {"lines": [
    {"account_code": "1500", "side": "debit"},
    {"account_code": "1000", "side": "credit"},
]}
EQUIP_RATIO = {"lines": [
    {"account_code": "1500", "ratio": 1.0},
    {"account_code": "1000", "ratio": 1.0},
]}


class TestExtractLabel:
    def test_extracts_structure_and_ratio(self):
        entry = _entry_with_structure(RENT_STRUCTURE, RENT_RATIO)
        label = extract_label(entry)
        assert len(label.structure) == 2
        assert label.structure[0].account_code == "5200"
        assert label.structure[0].side == "debit"
        assert label.ratio[0].ratio == 1.0

    def test_hash_is_deterministic(self):
        e1 = _entry_with_structure(RENT_STRUCTURE, RENT_RATIO)
        e2 = _entry_with_structure(RENT_STRUCTURE, RENT_RATIO)
        assert extract_label(e1).structure_hash == extract_label(e2).structure_hash

    def test_different_structures_different_hash(self):
        e1 = _entry_with_structure(RENT_STRUCTURE, RENT_RATIO)
        e2 = _entry_with_structure(EQUIP_STRUCTURE, EQUIP_RATIO)
        assert extract_label(e1).structure_hash != extract_label(e2).structure_hash


class TestExtractLabels:
    def test_extracts_all(self):
        entries = [_entry_with_structure(RENT_STRUCTURE, RENT_RATIO) for _ in range(5)]
        labels = extract_labels(entries)
        assert len(labels) == 5

    def test_empty_entries(self):
        assert extract_labels([]) == []


class TestFindMostCommon:
    def test_unanimous(self):
        entries = [_entry_with_structure(RENT_STRUCTURE, RENT_RATIO) for _ in range(9)]
        labels = extract_labels(entries)
        result = find_most_common(labels)
        assert result is not None
        label, k, n = result
        assert k == 9
        assert n == 9
        assert label.structure[0].account_code == "5200"

    def test_majority(self):
        entries = (
            [_entry_with_structure(RENT_STRUCTURE, RENT_RATIO)] * 7
            + [_entry_with_structure(EQUIP_STRUCTURE, EQUIP_RATIO)] * 2
        )
        labels = extract_labels(entries)
        result = find_most_common(labels)
        label, k, n = result
        assert k == 7
        assert n == 9
        assert label.structure[0].account_code == "5200"

    def test_empty_returns_none(self):
        assert find_most_common([]) is None

    def test_tie_returns_one(self):
        entries = (
            [_entry_with_structure(RENT_STRUCTURE, RENT_RATIO)] * 5
            + [_entry_with_structure(EQUIP_STRUCTURE, EQUIP_RATIO)] * 5
        )
        labels = extract_labels(entries)
        result = find_most_common(labels)
        assert result is not None
        _, k, n = result
        assert k == 5
        assert n == 10
