from __future__ import annotations

from services.normalizer.logic import NormalizationService


def _svc():
    return NormalizationService()


def test_extract_amount_invalid_existing():
    amount, confident = _svc().extract_amount({"amount": "not-a-num"}, [])
    assert confident is False


def test_normalize_message_from_filename_only():
    result = _svc().normalize({"filename": "data.csv", "source": "upload"})
    assert "data.csv" in result.description
    assert result.source == "upload"
