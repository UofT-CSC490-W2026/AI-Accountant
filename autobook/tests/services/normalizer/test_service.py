from __future__ import annotations

from services.normalizer.service import NormalizationService


def test_normalization_service_marks_ambiguous_amounts_as_not_confident() -> None:
    service = NormalizationService()

    normalized = service.normalize(
        {
            "input_text": "Paid invoice 100 and tax 13 on 03/22/2026",
            "source": "manual",
            "currency": "CAD",
        }
    )

    assert normalized.amount is None
    assert normalized.amount_confident is False
    assert normalized.transaction_date == "2026-03-22"
    assert normalized.normalized_description == "paid invoice 100 and tax 13 on 03/22/2026"
    assert [mention["value"] for mention in normalized.amount_mentions] == [100.0, 13.0]
    assert normalized.party_mentions == []
