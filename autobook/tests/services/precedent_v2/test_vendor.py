"""Tests for vendor name normalization."""
from services.precedent_v2.vendor import normalize_vendor


class TestNormalizeVendor:
    def test_lowercase(self):
        assert normalize_vendor("APPLE") == "apple"

    def test_strips_inc(self):
        assert normalize_vendor("Apple Inc.") == "apple"

    def test_strips_ltd(self):
        assert normalize_vendor("Shopify Ltd") == "shopify"

    def test_strips_llc(self):
        assert normalize_vendor("Acme LLC") == "acme"

    def test_strips_corporation(self):
        assert normalize_vendor("Ford Corporation") == "ford"

    def test_removes_punctuation(self):
        assert normalize_vendor("Kheela's Hardware") == "kheelas hardware"

    def test_collapses_whitespace(self):
        assert normalize_vendor("  Apple   Inc.  ") == "apple"

    def test_none_returns_empty(self):
        assert normalize_vendor(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_vendor("") == ""

    def test_same_vendor_different_formats(self):
        assert normalize_vendor("Apple Inc.") == normalize_vendor("APPLE INC")
        assert normalize_vendor("apple") == normalize_vendor("Apple Inc.")

    def test_preserves_meaningful_words(self):
        assert normalize_vendor("Tim Hortons") == "tim hortons"

    def test_strips_multiple_suffixes(self):
        assert normalize_vendor("Acme Corp. Inc.") == "acme"
