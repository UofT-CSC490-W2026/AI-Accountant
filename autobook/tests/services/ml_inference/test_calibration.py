from __future__ import annotations

from services.ml_inference.calibration import average_confidence, clamp_confidence


def test_clamp_none():
    assert clamp_confidence(None) == 0.0


def test_clamp_none_custom_default():
    assert clamp_confidence(None, default=0.5) == 0.5


def test_clamp_in_range():
    assert clamp_confidence(0.75) == 0.75


def test_clamp_above():
    assert clamp_confidence(1.5) == 1.0


def test_clamp_below():
    assert clamp_confidence(-0.3) == 0.0


def test_average_empty():
    assert average_confidence(default=0.6) == 0.6


def test_average_all_none():
    assert average_confidence(None, None, default=0.6) == 0.6


def test_average_mixed():
    result = average_confidence(0.8, None, 0.6)
    assert result == 0.7


def test_average_single():
    assert average_confidence(0.9) == 0.9
