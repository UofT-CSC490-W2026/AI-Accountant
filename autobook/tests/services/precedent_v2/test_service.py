"""8 integration tests for precedent_v2 — one per procedure step.

Each test runs through service.execute() end-to-end with mocked DB.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from services.precedent_v2.models import PrecedentEntry, compute_structure_hash
from services.precedent_v2.service import execute

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


def _entry(vendor: str, amount: float, structure=None, ratio=None):
    e = MagicMock(spec=PrecedentEntry)
    e.vendor = vendor
    e.amount = Decimal(str(amount))
    e.structure = structure or RENT_STRUCTURE
    e.ratio = ratio or RENT_RATIO
    e.structure_hash = compute_structure_hash(e.structure)
    return e


def _msg(vendor="Apple", amount=2000.0):
    return {
        "parse_id": "p1",
        "user_id": "u1",
        "counterparty": vendor,
        "amount": amount,
        "input_text": f"Paid {vendor} ${amount}",
        "transaction_date": "2026-03-28",
        "user_context": {"province": "ON"},
    }


def _patch(entries):
    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "user-1"
    return (
        patch("services.precedent_v2.service.SessionLocal", return_value=mock_db),
        patch("services.precedent_v2.service.resolve_local_user", return_value=mock_user),
        patch("services.precedent_v2.service.set_current_user_context"),
        patch("services.precedent_v2.service.PrecedentDAO.get_by_vendor", return_value=entries),
    )


def _run(entries, msg=None):
    msg = msg or _msg()
    p = _patch(entries)
    with p[0], p[1], p[2], p[3]:
        return execute(msg)


# ── 1. No candidate — vendor not found ───────────────────────────────────

def test_1_no_candidate():
    """No counterparty in message → abstain immediately."""
    result = execute({"parse_id": "p1", "user_id": "u1"})
    assert result["precedent_match"]["matched"] is False
    assert "no vendor" in result["precedent_match"]["reason"]


# ── 2. Candidates less than n_min ────────────────────────────────────────

def test_2_below_n_min():
    """8 entries for this vendor — below n_min=9 → abstain."""
    entries = [_entry("apple", 2000) for _ in range(8)]
    result = _run(entries)
    assert result["precedent_match"]["matched"] is False
    assert "need 9" in result["precedent_match"]["reason"]


# ── 3. Single-mode amount cluster — belongs ──────────────────────────────

def test_3_single_cluster_belongs():
    """9 entries all at ~$2000, transaction at $2000 → bypass."""
    entries = [_entry("apple", 2000) for _ in range(9)]
    result = _run(entries)
    assert result["precedent_match"]["matched"] is True
    assert result["precedent_match"]["confidence"] == 0.95
    assert result["proposed_entry"]["entry"]["origin_tier"] == 1


# ── 4. Single-mode amount cluster — does not belong ─────────────────────

def test_4_single_cluster_not_belongs():
    """9 entries at ~$100, transaction at $5000 → outside range → abstain."""
    entries = [_entry("apple", 100) for _ in range(9)]
    result = _run(entries, _msg(amount=5000.0))
    assert result["precedent_match"]["matched"] is False
    assert "outside" in result["precedent_match"]["reason"]


# ── 5. Multi-mode amount cluster — belongs to one ────────────────────────

def test_5_multi_cluster_belongs():
    """Two amount clusters (~$100, ~$2000). Transaction at $2050 → matches high cluster."""
    entries = (
        [_entry("apple", a) for a in [100, 105, 110] * 3]    # 9 entries ~$105
        + [_entry("apple", a) for a in [2000, 2050, 2100] * 3]  # 9 entries ~$2050
    )
    result = _run(entries, _msg(amount=2050.0))
    assert result["precedent_match"]["matched"] is True


# ── 6. Multi-mode amount cluster — does not belong ──────────────────────

def test_6_multi_cluster_not_belongs():
    """Two amount clusters (~$100, ~$2000). Transaction at $500 → between clusters → abstain."""
    entries = (
        [_entry("apple", a) for a in [100, 105, 110] * 3]
        + [_entry("apple", a) for a in [2000, 2050, 2100] * 3]
    )
    result = _run(entries, _msg(amount=500.0))
    assert result["precedent_match"]["matched"] is False
    assert "outside" in result["precedent_match"]["reason"]


# ── 7. Bayesian threshold — borderline fail ──────────────────────────────

def test_7_bayesian_borderline_fail():
    """8 rent + 1 equipment out of 9 → p = (8+0.5)/(9+1) = 0.85 < 0.95 → abstain."""
    entries = (
        [_entry("apple", 2000, RENT_STRUCTURE, RENT_RATIO)] * 8
        + [_entry("apple", 2000, EQUIP_STRUCTURE, EQUIP_RATIO)] * 1
    )
    result = _run(entries)
    assert result["precedent_match"]["matched"] is False
    assert "confidence" in result["precedent_match"]["reason"]


# ── 8. Bayesian threshold — borderline pass ──────────────────────────────

def test_8_bayesian_borderline_pass():
    """9 rent + 0 other out of 9 → p = (9+0.5)/(9+1) = 0.95 = threshold → bypass."""
    entries = [_entry("apple", 2000, RENT_STRUCTURE, RENT_RATIO)] * 9
    result = _run(entries)
    assert result["precedent_match"]["matched"] is True
    assert result["precedent_match"]["confidence"] == 0.95


# ── 9. Bayesian threshold — one dissenter passes at n=29 ─────────────────

def test_9_one_dissenter_passes_at_n29():
    """28 rent + 1 equipment out of 29 → first n where k=n-1 can pass 0.95 threshold."""
    entries = (
        [_entry("apple", 2000 + i * 0.01, RENT_STRUCTURE, RENT_RATIO) for i in range(28)]
        + [_entry("apple", 2000.28, EQUIP_STRUCTURE, EQUIP_RATIO)]
    )
    result = _run(entries)
    assert result["precedent_match"]["matched"] is True
    assert result["precedent_match"]["confidence"] >= 0.95
