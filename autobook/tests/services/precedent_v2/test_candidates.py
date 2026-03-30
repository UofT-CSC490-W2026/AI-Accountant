"""Tests for candidate filtering (n_min check)."""
from unittest.mock import MagicMock

from services.precedent_v2.candidates import N_MIN, filter_candidates
from services.precedent_v2.models import PrecedentEntry


def _make_entries(n: int) -> list:
    return [MagicMock(spec=PrecedentEntry) for _ in range(n)]


class TestFilterCandidates:
    def test_n_min_is_9(self):
        assert N_MIN == 9

    def test_returns_none_below_n_min(self):
        assert filter_candidates(_make_entries(8)) is None

    def test_returns_none_for_empty(self):
        assert filter_candidates([]) is None

    def test_returns_entries_at_n_min(self):
        entries = _make_entries(9)
        result = filter_candidates(entries)
        assert result is entries

    def test_returns_entries_above_n_min(self):
        entries = _make_entries(20)
        result = filter_candidates(entries)
        assert result is entries

    def test_custom_n_min(self):
        assert filter_candidates(_make_entries(3), n_min=5) is None
        assert filter_candidates(_make_entries(5), n_min=5) is not None
