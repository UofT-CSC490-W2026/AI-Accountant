from __future__ import annotations

import pytest

from accounting_engine.rules import (
    RuleEngineResult,
    build_rule_based_entry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(intent_label: str, amount: float = 100.0, **overrides) -> dict:
    """Build a minimal message dict for the rule engine."""
    msg = {"intent_label": intent_label, "amount": amount}
    msg.update(overrides)
    return msg


def _assert_debit_credit(result: RuleEngineResult, debit_code: str, credit_code: str, amount: float):
    lines = result.proposed_entry["lines"]
    assert len(lines) == 2
    debit_line = lines[0]
    credit_line = lines[1]
    assert debit_line["type"] == "debit"
    assert debit_line["account_code"] == debit_code
    assert debit_line["amount"] == amount
    assert credit_line["type"] == "credit"
    assert credit_line["account_code"] == credit_code
    assert credit_line["amount"] == amount


# ---------------------------------------------------------------------------
# Intent-based routing
# ---------------------------------------------------------------------------

class TestAssetPurchase:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("asset_purchase"), confidence=0.9, origin_tier=1)
        assert isinstance(result, RuleEngineResult)
        assert result.requires_human_review is False
        assert result.clarification_reason is None
        _assert_debit_credit(result, "1500", "1000", 100.0)
        assert "Equipment" in result.explanation

    def test_bank_category_equipment(self):
        result = build_rule_based_entry(
            {"bank_category": "equipment", "amount": 200.0},
            confidence=0.8,
            origin_tier=2,
        )
        assert result.requires_human_review is False
        _assert_debit_credit(result, "1500", "1000", 200.0)


class TestSoftwareSubscription:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("software_subscription", 49.99), confidence=0.9, origin_tier=1)
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5300", "1000", 49.99)
        assert "Software" in result.explanation

    def test_bank_category(self):
        result = build_rule_based_entry(
            {"bank_category": "software_subscription", "amount": 12.0},
            confidence=0.7,
            origin_tier=2,
        )
        _assert_debit_credit(result, "5300", "1000", 12.0)


class TestRentExpense:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("rent_expense", 1500.0), confidence=0.95, origin_tier=1)
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5200", "1000", 1500.0)
        assert "Rent" in result.explanation

    def test_bank_category_rent(self):
        result = build_rule_based_entry(
            {"bank_category": "rent", "amount": 2000.0},
            confidence=0.8,
            origin_tier=2,
        )
        _assert_debit_credit(result, "5200", "1000", 2000.0)


class TestMealsEntertainment:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("meals_entertainment", 75.0), confidence=0.85, origin_tier=1)
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5400", "1000", 75.0)
        assert "Meals" in result.explanation

    def test_bank_category(self):
        result = build_rule_based_entry(
            {"bank_category": "meals_entertainment", "amount": 30.0},
            confidence=0.6,
            origin_tier=2,
        )
        _assert_debit_credit(result, "5400", "1000", 30.0)


class TestProfessionalFees:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("professional_fees", 500.0), confidence=0.9, origin_tier=1)
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5430", "1000", 500.0)
        assert "Professional Fees" in result.explanation

    def test_bank_category(self):
        result = build_rule_based_entry(
            {"bank_category": "professional_fees", "amount": 250.0},
            confidence=0.7,
            origin_tier=2,
        )
        _assert_debit_credit(result, "5430", "1000", 250.0)


class TestBankFee:
    def test_intent_label(self):
        result = build_rule_based_entry(_msg("bank_fee", 15.0), confidence=0.95, origin_tier=1)
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5500", "1000", 15.0)
        assert "Bank Fee" in result.explanation

    def test_bank_category_bank_fees(self):
        result = build_rule_based_entry(
            {"bank_category": "bank_fees", "amount": 5.0},
            confidence=0.8,
            origin_tier=2,
        )
        _assert_debit_credit(result, "5500", "1000", 5.0)


# ---------------------------------------------------------------------------
# Fallback (unknown intent)
# ---------------------------------------------------------------------------

class TestFallback:
    def test_unknown_intent_no_transfer_destination(self):
        result = build_rule_based_entry(
            {"intent_label": "some_random_intent", "amount": 100.0},
            confidence=0.5,
            origin_tier=3,
        )
        assert result.requires_human_review is True
        assert result.clarification_reason == "Destination account is unclear."
        _assert_debit_credit(result, "9999", "1000", 100.0)
        assert "Unknown Destination" in result.explanation

    def test_unknown_intent_with_transfer_destination(self):
        result = build_rule_based_entry(
            {
                "intent_label": "wire_transfer",
                "amount": 5000.0,
                "entities": {"transfer_destination": "Savings Account"},
            },
            confidence=0.4,
            origin_tier=3,
        )
        assert result.requires_human_review is True
        assert result.clarification_reason == "Transfer destination account is not confidently mapped."
        _assert_debit_credit(result, "9999", "1000", 5000.0)

    def test_no_intent_label_at_all(self):
        result = build_rule_based_entry(
            {"amount": 42.0},
            confidence=0.3,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.clarification_reason == "Destination account is unclear."


# ---------------------------------------------------------------------------
# Missing / bad amount
# ---------------------------------------------------------------------------

class TestMissingAmount:
    def test_amount_none(self):
        result = build_rule_based_entry(
            {"intent_label": "asset_purchase"},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.clarification_reason == "Amount is missing or ambiguous."
        assert result.proposed_entry["lines"] == []

    def test_amount_zero(self):
        result = build_rule_based_entry(
            {"intent_label": "asset_purchase", "amount": 0},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.proposed_entry["lines"] == []

    def test_amount_negative(self):
        result = build_rule_based_entry(
            {"intent_label": "asset_purchase", "amount": -50.0},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.proposed_entry["lines"] == []

    def test_amount_non_numeric_string(self):
        result = build_rule_based_entry(
            {"intent_label": "asset_purchase", "amount": "not-a-number"},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.proposed_entry["lines"] == []

    def test_amount_from_entities(self):
        """Amount resolved from entities.amount when top-level amount is missing."""
        result = build_rule_based_entry(
            {"intent_label": "asset_purchase", "entities": {"amount": 300.0}},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is False
        _assert_debit_credit(result, "1500", "1000", 300.0)

    def test_amount_from_single_amount_mention(self):
        """Amount resolved from amount_mentions when top-level + entities are missing."""
        result = build_rule_based_entry(
            {"intent_label": "rent_expense", "amount_mentions": [{"value": 1200.0}]},
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is False
        _assert_debit_credit(result, "5200", "1000", 1200.0)

    def test_multiple_amount_mentions_is_ambiguous(self):
        """Two amount_mentions => ambiguous => missing amount path."""
        result = build_rule_based_entry(
            {
                "intent_label": "rent_expense",
                "amount_mentions": [{"value": 100.0}, {"value": 200.0}],
            },
            confidence=0.9,
            origin_tier=1,
        )
        assert result.requires_human_review is True
        assert result.proposed_entry["lines"] == []


# ---------------------------------------------------------------------------
# Entry metadata
# ---------------------------------------------------------------------------

class TestEntryMetadata:
    def test_metadata_fields(self):
        result = build_rule_based_entry(
            {
                "intent_label": "bank_fee",
                "amount": 10.0,
                "transaction_id": "tx-123",
                "input_text": "Monthly bank fee",
                "transaction_date": "2026-01-15",
            },
            confidence=0.92,
            origin_tier=1,
        )
        entry = result.proposed_entry["entry"]
        assert entry["date"] == "2026-01-15"
        assert entry["description"] == "Monthly bank fee"
        assert entry["origin_tier"] == 1
        assert entry["confidence"] == 0.92
        assert entry["transaction_id"] == "tx-123"
        assert entry["rationale"] is None

    def test_description_fallback_chain(self):
        """description falls back through input_text -> description -> normalized_text -> default."""
        result = build_rule_based_entry(
            {"intent_label": "bank_fee", "amount": 5.0, "normalized_text": "bank svc charge"},
            confidence=0.5,
            origin_tier=2,
        )
        assert result.proposed_entry["entry"]["description"] == "bank svc charge"

    def test_description_default(self):
        result = build_rule_based_entry(
            {"intent_label": "bank_fee", "amount": 5.0},
            confidence=0.5,
            origin_tier=2,
        )
        assert result.proposed_entry["entry"]["description"] == "Autobook generated entry"

    def test_no_transaction_id_omitted(self):
        result = build_rule_based_entry(
            {"intent_label": "bank_fee", "amount": 5.0},
            confidence=0.5,
            origin_tier=2,
        )
        assert "transaction_id" not in result.proposed_entry["entry"]


# ---------------------------------------------------------------------------
# RuleEngineResult is frozen dataclass
# ---------------------------------------------------------------------------

class TestRuleEngineResultFrozen:
    def test_cannot_mutate(self):
        result = build_rule_based_entry(_msg("bank_fee", 10.0), confidence=0.9, origin_tier=1)
        with pytest.raises(AttributeError):
            result.requires_human_review = True
