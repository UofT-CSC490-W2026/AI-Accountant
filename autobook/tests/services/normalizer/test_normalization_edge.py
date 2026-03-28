"""Edge case tests for services/shared/normalization.py — covers uncovered branches."""
from __future__ import annotations

from services.shared.normalization import NormalizationService


svc = NormalizationService()


def test_duplicate_date_mention_skipped():
    """Line 99: second occurrence of same date string is skipped."""
    mentions = svc.extract_date_mentions("Invoice 2026-03-15 paid 2026-03-15")
    assert len(mentions) == 1
    assert mentions[0]["value"] == "2026-03-15"


def test_duplicate_party_mention_skipped():
    """Line 127: second occurrence of same party is skipped."""
    mentions = svc.extract_party_mentions("paid Apple for laptop from Apple")
    values = [m["value"] for m in mentions]
    assert values.count("Apple") == 1


def test_duplicate_quantity_mention_skipped():
    """Line 142: second occurrence of same (quantity, noun) is skipped."""
    mentions = svc.extract_quantity_mentions("bought 5 chairs and 5 chairs")
    matching = [m for m in mentions if m["unit"] == "chairs"]
    assert len(matching) == 1


def test_extract_date_mm_dd_yyyy_format():
    """Line 193: MM/DD/YYYY date format parsed correctly."""
    result = svc.extract_transaction_date({}, "Invoice from 03/15/2026")
    assert result == "2026-03-15"


def test_extract_date_invalid_format_returns_raw():
    """Line 195: invalid date format returns raw string."""
    result = svc.extract_transaction_date({}, "Due on 99/99/9999")
    assert result == "99/99/9999"
