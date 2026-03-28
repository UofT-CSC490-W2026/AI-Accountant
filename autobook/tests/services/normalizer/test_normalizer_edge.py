from __future__ import annotations

from services.normalizer.logic import NormalizationService


def _svc():
    return NormalizationService()


def test_amount_from_bare_number():
    mentions = _svc().extract_amount_mentions("invoice total 500")
    assert any(m["value"] == 500.0 for m in mentions)


def test_amount_skips_year():
    mentions = _svc().extract_amount_mentions("invoice from 2026")
    assert not any(m["value"] == 2026.0 for m in mentions)


def test_date_parse_error_fallback():
    mentions = _svc().extract_date_mentions("date is 99/99/9999")
    for m in mentions:
        assert "value" in m


def test_normalize_filename_description():
    result = _svc().normalize({"filename": "march-bank.csv", "source": "csv"})
    assert "march-bank.csv" in result.description


def test_normalize_default_description():
    result = _svc().normalize({"source": "manual"})
    assert result.description == "Autobook transaction"


def test_extract_amount_existing():
    amount, confident = _svc().extract_amount({"amount": "250.00"}, [])
    assert amount == 250.0
    assert confident is True


def test_extract_amount_invalid():
    amount, confident = _svc().extract_amount({"amount": "not-a-number"}, [])
    assert amount is None
    assert confident is False
