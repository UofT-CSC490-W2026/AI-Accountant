from __future__ import annotations

from accounting_engine.rules import build_rule_based_entry


def test_execute_equipment():
    result = build_rule_based_entry(
        {"input_text": "Bought printer for $500", "intent_label": "asset_purchase", "amount": 500, "entities": {}},
        confidence=0.97, origin_tier=2,
    )
    lines = result.proposed_entry["lines"]
    assert not result.requires_human_review
    assert lines[0]["account_name"] == "Equipment"
    assert lines[0]["type"] == "debit"
    assert lines[0]["amount"] == 500.0
    assert lines[1]["account_name"] == "Cash"
    assert lines[1]["type"] == "credit"


def test_execute_software():
    result = build_rule_based_entry(
        {"input_text": "Paid Slack", "intent_label": "software_subscription", "amount": 39, "entities": {}},
        confidence=0.95, origin_tier=2,
    )
    lines = result.proposed_entry["lines"]
    assert not result.requires_human_review
    assert lines[0]["account_name"] == "Software & Subscriptions"
    assert lines[0]["amount"] == 39.0


def test_execute_rent():
    result = build_rule_based_entry(
        {"input_text": "Monthly rent", "intent_label": "rent_expense", "amount": 1800, "entities": {}},
        confidence=0.95, origin_tier=2,
    )
    assert not result.requires_human_review
    assert result.proposed_entry["lines"][0]["account_name"] == "Rent Expense"


def test_execute_meals():
    result = build_rule_based_entry(
        {"input_text": "Team dinner", "intent_label": "meals_entertainment", "amount": 200, "entities": {}},
        confidence=0.9, origin_tier=2,
    )
    assert not result.requires_human_review
    assert result.proposed_entry["lines"][0]["account_name"] == "Meals & Entertainment"


def test_execute_professional():
    result = build_rule_based_entry(
        {"input_text": "Legal consultation", "intent_label": "professional_fees", "amount": 2000, "entities": {}},
        confidence=0.92, origin_tier=2,
    )
    assert not result.requires_human_review
    assert result.proposed_entry["lines"][0]["account_name"] == "Professional Fees"


def test_execute_bank_fee():
    result = build_rule_based_entry(
        {"input_text": "Monthly bank service fee", "intent_label": "bank_fee", "amount": 15, "entities": {}},
        confidence=0.45, origin_tier=2,
    )
    assert not result.requires_human_review
    assert result.proposed_entry["lines"][0]["account_name"] == "Bank Fees"


def test_process_high_confidence():
    result = build_rule_based_entry(
        {"input_text": "Bought printer for $500", "intent_label": "asset_purchase", "amount": 500, "entities": {}},
        confidence=0.97, origin_tier=2,
    )
    assert not result.requires_human_review
    assert len(result.proposed_entry["lines"]) == 2


def test_process_low_confidence_no_amount():
    result = build_rule_based_entry(
        {"input_text": "Something unclear happened", "entities": {}},
        confidence=0.45, origin_tier=2,
    )
    assert result.requires_human_review
    assert result.proposed_entry["lines"] == []


def test_process_threshold_boundary():
    result = build_rule_based_entry(
        {"input_text": "Paid Slack", "intent_label": "software_subscription", "amount": 39, "entities": {}},
        confidence=0.95, origin_tier=2,
    )
    assert not result.requires_human_review
    assert len(result.proposed_entry["lines"]) == 2


def test_execute_unknown_intent_no_amount():
    result = build_rule_based_entry(
        {"input_text": "Something unclear happened", "entities": {}},
        confidence=0.45, origin_tier=2,
    )
    assert result.requires_human_review
    assert result.proposed_entry["lines"] == []
