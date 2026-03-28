from __future__ import annotations

from services.ml_inference.providers.heuristic import BaselineInferenceService


def _svc():
    return BaselineInferenceService()


def test_extract_amount_from_regex():
    result = _svc().extract_amount({}, "$1,234.56")
    assert result == 1234.56


def test_extract_amount_bare_number():
    result = _svc().extract_amount({}, "invoice total 500")
    assert result == 500.0


def test_extract_amount_multiple_mentions_none():
    result = _svc().extract_amount({"amount_mentions": [{"value": 100}, {"value": 200}]}, "")
    assert result is None


def test_extract_amount_invalid_existing():
    result = _svc().extract_amount({"amount": "bad"}, "")
    assert result is None


def test_classify_bank_meals():
    result = _svc().classify_bank_transaction("team dinner", "meals_entertainment")
    assert result.label == "meals_entertainment"


def test_classify_bank_professional():
    result = _svc().classify_bank_transaction("legal advice", "professional_fees")
    assert result.label == "professional_fees"


def test_classify_bank_rent():
    result = _svc().classify_bank_transaction("monthly rent", "rent_expense")
    assert result.label == "rent"


def test_classify_bank_software():
    result = _svc().classify_bank_transaction("slack sub", "software_subscription")
    assert result.label == "software_subscription"
