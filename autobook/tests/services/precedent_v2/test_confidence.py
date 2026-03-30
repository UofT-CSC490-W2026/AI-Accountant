"""Tests for Jeffreys confidence and threshold check."""
from services.precedent_v2.confidence import (
    THRESHOLD, JEFFREYS_ALPHA, JEFFREYS_BETA,
    jeffreys_confidence, check_threshold,
)


class TestJeffreysConfidence:
    def test_unanimous_9_of_9(self):
        # (9 + 0.5) / (9 + 1) = 9.5 / 10 = 0.95
        assert jeffreys_confidence(9, 9) == 0.95

    def test_unanimous_10_of_10(self):
        # (10 + 0.5) / (10 + 1) = 10.5 / 11 ≈ 0.9545
        p = jeffreys_confidence(10, 10)
        assert p > 0.95

    def test_8_of_9(self):
        # (8 + 0.5) / (9 + 1) = 8.5 / 10 = 0.85
        assert jeffreys_confidence(8, 9) == 0.85

    def test_zero_of_zero(self):
        # (0 + 0.5) / (0 + 1) = 0.5
        assert jeffreys_confidence(0, 0) == 0.5

    def test_zero_of_n(self):
        # (0 + 0.5) / (9 + 1) = 0.05
        assert jeffreys_confidence(0, 9) == 0.05

    def test_all_of_1(self):
        # (1 + 0.5) / (1 + 1) = 0.75
        assert jeffreys_confidence(1, 1) == 0.75

    def test_uses_jeffreys_prior(self):
        assert JEFFREYS_ALPHA == 0.5
        assert JEFFREYS_BETA == 0.5


class TestCheckThreshold:
    def test_at_threshold(self):
        assert check_threshold(0.95) is True

    def test_above_threshold(self):
        assert check_threshold(0.96) is True

    def test_below_threshold(self):
        assert check_threshold(0.94) is False

    def test_default_threshold_is_095(self):
        assert THRESHOLD == 0.95

    def test_custom_threshold(self):
        assert check_threshold(0.80, threshold=0.80) is True
        assert check_threshold(0.79, threshold=0.80) is False

    def test_n_min_9_is_minimum_for_bypass(self):
        # With k=n (unanimous), the minimum n where p >= 0.95 is n=9
        for n in range(1, 9):
            assert jeffreys_confidence(n, n) < 0.95, f"n={n} should be below threshold"
        assert jeffreys_confidence(9, 9) >= 0.95
