"""Tests for flywheel service — tier-based learning after posting."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.flywheel.service import execute, _infer_tier


def _msg(origin_tier=None, **overrides):
    msg = {
        "parse_id": "p1",
        "user_id": "u1",
        "transaction_id": "t1",
        "journal_entry_id": "je1",
        "counterparty": "Apple",
        "amount": 2000.0,
        "input_text": "Paid Apple $2000",
        "intent_label": "asset_purchase",
        "proposed_entry": {
            "entry": {"origin_tier": origin_tier or 3},
            "lines": [
                {"account_code": "1500", "type": "debit", "amount": 2000.0},
                {"account_code": "1000", "type": "credit", "amount": 2000.0},
            ],
        },
        "confidence": {"overall": 0.97},
    }
    if origin_tier is not None:
        msg["origin_tier"] = origin_tier
    msg.update(overrides)
    return msg


def _patches():
    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "user-1"
    return (
        patch("services.flywheel.service.SessionLocal", return_value=mock_db),
        patch("services.flywheel.service.resolve_local_user", return_value=mock_user),
        patch("services.flywheel.service.set_current_user_context"),
        patch("services.flywheel.service.write_pattern"),
        patch("services.flywheel.service.TrainingDataDAO"),
        patch("services.flywheel.service.write_calibration_pair"),
        patch("services.flywheel.service.index_positive_example"),
        patch("services.flywheel.service.index_correction_example"),
    )


def test_t1_does_nothing():
    msg = _msg(origin_tier=1)
    p = _patches()
    with p[0], p[1], p[2], p[3] as pattern, p[4] as training, p[5] as calib, p[6] as pos, p[7] as corr:
        execute(msg)
    pattern.assert_not_called()
    training.append.assert_not_called()
    calib.assert_not_called()
    pos.assert_not_called()
    corr.assert_not_called()


def test_t2_writes_pattern_only():
    msg = _msg(origin_tier=2)
    p = _patches()
    with p[0], p[1], p[2], p[3] as pattern, p[4] as training, p[5] as calib, p[6] as pos, p[7] as corr:
        execute(msg)
    pattern.assert_called_once()
    training.append.assert_not_called()
    calib.assert_not_called()
    pos.assert_not_called()


def test_t3_writes_pattern_and_training():
    msg = _msg(origin_tier=3)
    p = _patches()
    with p[0], p[1], p[2], p[3] as pattern, p[4] as training, p[5] as calib, p[6] as pos, p[7] as corr:
        execute(msg)
    pattern.assert_called_once()
    training.append.assert_called_once()
    calib.assert_not_called()
    pos.assert_not_called()


def test_t4_writes_all():
    msg = _msg(origin_tier=4)
    p = _patches()
    with p[0], p[1], p[2], p[3] as pattern, p[4] as training, p[5] as calib, p[6] as pos, p[7] as corr:
        execute(msg)
    pattern.assert_called_once()
    training.append.assert_called_once()
    calib.assert_called_once()
    pos.assert_called_once()
    corr.assert_not_called()  # no edit action


def test_t4_correction_indexes_both():
    msg = _msg(origin_tier=4, clarification_action="edit", error_description="wrong account")
    p = _patches()
    with p[0], p[1], p[2], p[3], p[4], p[5], p[6] as pos, p[7] as corr:
        execute(msg)
    pos.assert_called_once()
    corr.assert_called_once()


def test_infer_tier_from_proposed_entry():
    msg = _msg(origin_tier=3)
    del msg["origin_tier"]
    assert _infer_tier(msg) == 3


def test_infer_tier_default():
    assert _infer_tier({}) == 3
