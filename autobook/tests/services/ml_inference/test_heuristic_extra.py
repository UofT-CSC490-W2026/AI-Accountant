from __future__ import annotations

from services.ml_inference.providers.heuristic import BaselineInferenceService


def _svc():
    return BaselineInferenceService()


def test_classify_intent_upload_source():
    result = _svc().classify_intent("unknown transaction", "csv_upload")
    assert result.label == "bank_transaction"


def test_classify_intent_general_expense():
    result = _svc().classify_intent("miscellaneous charge", "manual_text")
    assert result.label == "general_expense"


def test_classify_bank_transaction_no_match():
    result = _svc().classify_bank_transaction("misc charge", None)
    assert result.label is None


def test_classify_bank_transaction_fee_in_text():
    result = _svc().classify_bank_transaction("monthly fee charged", None)
    assert result.label == "bank_fees"


def test_match_cca_class_desk():
    result = _svc().match_cca_class("asset_purchase", "desk")
    assert result.label == "class_8"


def test_match_cca_class_default():
    result = _svc().match_cca_class("asset_purchase", "machinery")
    assert result.label == "class_8"
    assert result.confidence == 0.72


def test_extract_vendor_from_text():
    result = _svc().extract_vendor("bought a laptop from apple")
    assert result == "Apple"


def test_extract_transfer_destination():
    result = _svc().extract_transfer_destination("transferred to savings")
    assert result == "Savings"


def test_extract_transfer_destination_filtered():
    result = _svc().extract_transfer_destination("transferred to cash")
    assert result is None


def test_extract_quantity():
    result = _svc().extract_quantity({"quantity_mentions": [{"value": 5, "unit": "chairs"}]})
    assert result == 5


def test_extract_quantity_none():
    result = _svc().extract_quantity({})
    assert result is None


def test_extract_mentioned_date():
    result = _svc().extract_mentioned_date_from_message({"date_mentions": [{"value": "2026-03-22"}]}, "")
    assert result == "2026-03-22"


def test_extract_mentioned_date_from_text():
    result = _svc().extract_mentioned_date_from_message({}, "paid on 03/22/2026")
    assert result is not None


def test_enrich_full():
    result = _svc().enrich({
        "input_text": "Bought printer from Apple for $500",
        "source": "manual",
        "currency": "CAD",
    })
    assert result["intent_label"] == "asset_purchase"
    assert "confidence" in result
    assert result["entities"]["vendor"] == "Apple"
