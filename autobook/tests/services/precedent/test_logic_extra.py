from __future__ import annotations

from services.precedent.logic import (
    PrecedentCandidate,
    PrecedentMatch,
    _amount_matches,
    _token_overlap_ratio,
    find_precedent_match,
)


def test_amount_matches_true():
    assert _amount_matches(100.0, 100.0) is True


def test_amount_matches_close():
    assert _amount_matches(100.0, 100.004) is True


def test_amount_matches_false():
    assert _amount_matches(100.0, 200.0) is False


def test_amount_matches_none():
    assert _amount_matches(None, 100.0) is False
    assert _amount_matches(100.0, None) is False


def test_token_overlap_full():
    assert _token_overlap_ratio("bought laptop apple", "bought laptop apple") == 1.0


def test_token_overlap_partial():
    ratio = _token_overlap_ratio("bought laptop apple", "bought printer apple")
    assert 0.5 <= ratio < 1.0


def test_token_overlap_empty():
    assert _token_overlap_ratio("", "hello") == 0.0


def test_find_match_high_overlap_not_exact():
    match = find_precedent_match(
        {"normalized_description": "bought a laptop from apple for $2400", "amount": 2400.0, "counterparty": "Apple", "source": "manual_text"},
        [
            PrecedentCandidate(
                pattern_id="je:1",
                normalized_description="bought a laptop from apple for $2500",
                amount=2400.0,
                counterparty="Apple",
                source="manual_text",
                lines=[],
            )
        ],
    )
    # high overlap (0.35) + amount (0.2) + counterparty (0.1) + source (0.05) + partial description = 0.7+
    assert match.matched is False  # 0.7 is below 0.85 threshold — no match


def test_find_match_below_threshold():
    match = find_precedent_match(
        {"normalized_description": "completely different transaction"},
        [
            PrecedentCandidate(
                pattern_id="je:1",
                normalized_description="paid annual insurance premium",
                amount=None,
                counterparty=None,
                source=None,
                lines=[],
            )
        ],
    )
    assert match.matched is False
