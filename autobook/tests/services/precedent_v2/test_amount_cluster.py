"""Tests for amount clustering (Ckmeans) and cluster assignment."""
from decimal import Decimal
from unittest.mock import MagicMock

from services.precedent_v2.amount_cluster import assign_to_cluster, cluster_amounts
from services.precedent_v2.models import PrecedentEntry


def _entry(amount: float) -> MagicMock:
    e = MagicMock(spec=PrecedentEntry)
    e.amount = Decimal(str(amount))
    return e


class TestClusterAmounts:
    def test_single_cluster(self):
        entries = [_entry(100) for _ in range(9)]
        clusters = cluster_amounts(entries)
        assert len(clusters) == 1
        assert len(clusters[0].entries) == 9

    def test_two_clusters(self):
        entries = [_entry(a) for a in [100, 105, 110] * 3 + [500, 510, 520] * 3]
        clusters = cluster_amounts(entries)
        assert len(clusters) == 2
        centers = sorted(c.center for c in clusters)
        assert centers[0] < 200
        assert centers[1] > 400

    def test_cluster_bounds(self):
        entries = [_entry(a) for a in [100, 200, 300] * 3]
        clusters = cluster_amounts(entries)
        for c in clusters:
            assert c.lower <= c.center <= c.upper

    def test_max_k_limits_clusters(self):
        # 9 entries with n_min=9 → max_k=1, so only 1 cluster
        entries = [_entry(a) for a in [10, 20, 30, 40, 50, 60, 70, 80, 90]]
        clusters = cluster_amounts(entries, n_min=9)
        assert len(clusters) == 1


class TestAssignToCluster:
    def _make_clusters(self):
        entries_low = [_entry(a) for a in [100, 105, 110] * 3]
        entries_high = [_entry(a) for a in [500, 510, 520] * 3]
        return cluster_amounts(entries_low + entries_high)

    def test_assigns_to_correct_cluster(self):
        clusters = self._make_clusters()
        result = assign_to_cluster(103.0, clusters)
        assert result is not None
        assert result.center < 200

    def test_assigns_to_high_cluster(self):
        clusters = self._make_clusters()
        result = assign_to_cluster(515.0, clusters)
        assert result is not None
        assert result.center > 400

    def test_returns_none_outside_all_ranges(self):
        clusters = self._make_clusters()
        assert assign_to_cluster(300.0, clusters) is None

    def test_returns_none_below_all_ranges(self):
        clusters = self._make_clusters()
        assert assign_to_cluster(1.0, clusters) is None

    def test_returns_none_above_all_ranges(self):
        clusters = self._make_clusters()
        assert assign_to_cluster(10000.0, clusters) is None

    def test_returns_none_if_cluster_too_small(self):
        # Make a cluster with only 2 entries
        entries = [_entry(100), _entry(100)]
        clusters = cluster_amounts(entries, n_min=2)
        # But require n_min=9 for assignment
        assert assign_to_cluster(100.0, clusters, n_min=9) is None

    def test_exact_boundary_match(self):
        clusters = self._make_clusters()
        # Exact min of low cluster
        result = assign_to_cluster(100.0, clusters)
        assert result is not None
