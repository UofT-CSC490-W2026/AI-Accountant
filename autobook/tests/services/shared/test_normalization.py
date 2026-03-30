from __future__ import annotations

from datetime import date

from services.shared.normalization import NormalizationService


def test_canonicalize_source_maps_known_aliases() -> None:
    service = NormalizationService()

    assert service.canonicalize_source("manual") == "manual_text"
    assert service.canonicalize_source(" CSV ") == "csv_upload"
    assert service.canonicalize_source("bank_feed") == "bank_feed"


def test_normalize_text_collapses_internal_whitespace() -> None:
    service = NormalizationService()

    assert service.normalize_text("  Paid\t\tApple\n  For  2400 ") == "paid apple for 2400"


def test_extract_amount_mentions_deduplicates_regex_and_numeric_matches() -> None:
    service = NormalizationService()

    mentions = service.extract_amount_mentions("Paid Apple $2,400 and confirmed 2400 on the same line")

    assert mentions == [{"text": "$2,400", "value": 2400.0}]


def test_extract_amount_mentions_ignores_date_tokens() -> None:
    service = NormalizationService()

    mentions = service.extract_amount_mentions("Paid rent on 2026-03-22 for 1800")

    assert mentions == [{"text": "1800", "value": 1800.0}]


def test_extract_amount_prefers_valid_explicit_amount() -> None:
    service = NormalizationService()

    amount, confident = service.extract_amount({"amount": "2400.50"}, [{"text": "$2400.50", "value": 2400.5}])

    assert amount == 2400.5
    assert confident is True


def test_extract_amount_invalid_explicit_falls_back_to_single_mention() -> None:
    service = NormalizationService()

    amount, confident = service.extract_amount({"amount": "not-a-number"}, [{"text": "$99", "value": 99.0}])

    assert amount == 99.0
    assert confident is True


def test_extract_amount_returns_not_confident_for_multiple_mentions() -> None:
    service = NormalizationService()

    amount, confident = service.extract_amount(
        {},
        [{"text": "$100", "value": 100.0}, {"text": "$150", "value": 150.0}],
    )

    assert amount is None
    assert confident is False


def test_extract_date_mentions_normalizes_slash_dates_and_keeps_invalid_raw_value() -> None:
    service = NormalizationService()

    mentions = service.extract_date_mentions("Paid on 03/07/2026 and referenced 13/40/2026")

    assert mentions == [
        {"text": "03/07/2026", "value": "2026-03-07"},
        {"text": "13/40/2026", "value": "13/40/2026"},
    ]


def test_extract_party_mentions_filters_non_party_tokens() -> None:
    service = NormalizationService()

    mentions = service.extract_party_mentions("Paid cash for 80 and paid Apple for 120")

    assert mentions == [{"text": "Apple", "value": "Apple"}]


def test_extract_counterparty_prefers_explicit_message_value() -> None:
    service = NormalizationService()

    counterparty = service.extract_counterparty(
        {"counterparty": "Pilot Coffee Roasters"},
        [{"text": "Apple", "value": "Apple"}],
    )

    assert counterparty == "Pilot Coffee Roasters"


def test_extract_quantity_mentions_ignores_currency_units_and_deduplicates() -> None:
    service = NormalizationService()

    mentions = service.extract_quantity_mentions("Bought 3 laptops, 3 laptops, and paid 2400 CAD on invoice 88")

    assert mentions == [{"text": "3 laptops", "value": 3, "unit": "laptops"}]


def test_extract_transaction_date_prefers_existing_message_value() -> None:
    service = NormalizationService()

    transaction_date = service.extract_transaction_date(
        {"transaction_date": "2026-03-20"},
        "Paid on 03/07/2026",
        [{"text": "03/07/2026", "value": "2026-03-07"}],
    )

    assert transaction_date == "2026-03-20"


def test_extract_transaction_date_uses_precomputed_mentions_before_reparsing() -> None:
    service = NormalizationService()

    transaction_date = service.extract_transaction_date(
        {},
        "Paid on 03/07/2026",
        [{"text": "03/07/2026", "value": "2026-03-07"}],
    )

    assert transaction_date == "2026-03-07"


def test_normalize_uses_filename_fallback_defaults_and_single_mentions() -> None:
    service = NormalizationService()

    candidate = service.normalize(
        {
            "filename": "statement.pdf",
            "source": "pdf",
        }
    )

    assert candidate.description == "Uploaded file: statement.pdf"
    assert candidate.normalized_description == "uploaded file: statement.pdf"
    assert candidate.currency == "CAD"
    assert candidate.source == "pdf_upload"
    assert candidate.transaction_date == str(date.today())
    assert candidate.amount is None
    assert candidate.counterparty is None


def test_normalize_builds_mentions_for_standard_manual_text() -> None:
    service = NormalizationService()

    candidate = service.normalize(
        {
            "input_text": "Bought a laptop from Apple for $2400 on 2026-03-14",
            "source": "manual",
            "currency": "USD",
        }
    )

    assert candidate.amount == 2400.0
    assert candidate.amount_confident is True
    assert candidate.counterparty == "Apple"
    assert candidate.transaction_date == "2026-03-14"
    assert candidate.source == "manual_text"
    assert candidate.currency == "USD"
    assert candidate.party_mentions == [{"text": "Apple", "value": "Apple"}]
