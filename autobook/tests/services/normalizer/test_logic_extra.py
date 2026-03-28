from __future__ import annotations

from services.normalizer.logic import NormalizationService


def _svc():
    return NormalizationService()


def test_extract_quantity_mentions():
    mentions = _svc().extract_quantity_mentions("bought 5 chairs and 3 desks")
    assert len(mentions) == 2
    values = {(m["value"], m["unit"]) for m in mentions}
    assert (5, "chairs") in values
    assert (3, "desks") in values


def test_extract_quantity_filters_units():
    mentions = _svc().extract_quantity_mentions("paid 100 cash")
    assert len(mentions) == 0


def test_extract_party_mentions():
    mentions = _svc().extract_party_mentions("Paid Apple for software")
    assert len(mentions) == 1
    assert mentions[0]["value"] == "Apple"


def test_extract_party_filters_tokens():
    mentions = _svc().extract_party_mentions("paid cash for rent")
    assert len(mentions) == 0


def test_extract_date_mentions_iso():
    mentions = _svc().extract_date_mentions("invoice dated 2026-03-22")
    assert len(mentions) == 1
    assert mentions[0]["value"] == "2026-03-22"


def test_extract_date_mentions_slash():
    mentions = _svc().extract_date_mentions("paid on 03/22/2026")
    assert len(mentions) == 1
    assert mentions[0]["value"] == "2026-03-22"


def test_canonicalize_source():
    assert _svc().canonicalize_source("manual") == "manual_text"
    assert _svc().canonicalize_source("csv") == "csv_upload"
    assert _svc().canonicalize_source("pdf") == "pdf_upload"
    assert _svc().canonicalize_source(None) == "manual_text"


def test_extract_counterparty_explicit():
    result = _svc().extract_counterparty({"counterparty": "Apple"}, [])
    assert result == "Apple"


def test_extract_counterparty_from_mentions():
    result = _svc().extract_counterparty({}, [{"text": "Apple", "value": "Apple"}])
    assert result == "Apple"


def test_extract_counterparty_none():
    result = _svc().extract_counterparty({}, [])
    assert result is None


def test_extract_transaction_date_existing():
    result = _svc().extract_transaction_date({"transaction_date": "2026-01-01"}, "")
    assert result == "2026-01-01"


def test_extract_transaction_date_from_text():
    result = _svc().extract_transaction_date({}, "paid on 03/22/2026")
    assert result == "2026-03-22"


def test_normalize_only_path():
    from services.normalizer.service import execute
    result = execute({
        "parse_id": "p1",
        "input_text": "Bought item for $100",
        "source": "manual",
        "currency": "CAD",
        "store": False,
    })
    assert "transaction_id" not in result
    assert result["amount"] == 100.0
