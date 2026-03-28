from __future__ import annotations

import pytest

from accounting_engine.validators.journal_entry import validate_journal_entry
from accounting_engine.validators.tax import validate_tax
from accounting_engine.tools import vendor_history_lookup, coa_lookup, tax_rules_lookup


# ===========================================================================
# validate_journal_entry
# ===========================================================================

class TestValidJournalEntry:
    def test_balanced_two_line_entry(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 100.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_balanced_multi_line_entry(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 50.0},
                {"account_name": "AR", "type": "debit", "amount": 50.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_integer_amounts_accepted(self):
        entry = {
            "lines": [
                {"account_name": "Equipment", "type": "debit", "amount": 500},
                {"account_name": "Cash", "type": "credit", "amount": 500},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is True


class TestMissingLines:
    def test_no_lines_key(self):
        result = validate_journal_entry({})
        assert result["valid"] is False
        assert any("Missing or empty" in e for e in result["errors"])

    def test_lines_is_none(self):
        result = validate_journal_entry({"lines": None})
        assert result["valid"] is False

    def test_lines_is_empty_list(self):
        result = validate_journal_entry({"lines": []})
        assert result["valid"] is False

    def test_lines_is_not_a_list(self):
        result = validate_journal_entry({"lines": "not a list"})
        assert result["valid"] is False


class TestBadLineType:
    def test_invalid_type_value(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "invalid", "amount": 100.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("type must be" in e for e in result["errors"])

    def test_missing_type_field(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "amount": 100.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("missing 'type'" in e for e in result["errors"])


class TestNegativeAmount:
    def test_negative_amount(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": -50.0},
                {"account_name": "Revenue", "type": "credit", "amount": -50.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("must be > 0" in e for e in result["errors"])

    def test_zero_amount(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 0},
                {"account_name": "Revenue", "type": "credit", "amount": 0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False

    def test_non_numeric_amount(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": "abc"},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("must be a number" in e for e in result["errors"])


class TestUnbalanced:
    def test_debits_exceed_credits(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 200.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("Debits" in e and "Credits" in e for e in result["errors"])

    def test_credits_exceed_debits(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 50.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False

    def test_within_tolerance_is_valid(self):
        """Difference <= 0.005 is tolerated."""
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 100.004},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is True

    def test_just_outside_tolerance_is_invalid(self):
        """Difference > 0.005 is flagged."""
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit", "amount": 100.006},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False


class TestMissingRequiredFields:
    def test_missing_account_name(self):
        entry = {
            "lines": [
                {"type": "debit", "amount": 100.0},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("missing 'account_name'" in e for e in result["errors"])

    def test_missing_amount(self):
        entry = {
            "lines": [
                {"account_name": "Cash", "type": "debit"},
                {"account_name": "Revenue", "type": "credit", "amount": 100.0},
            ]
        }
        result = validate_journal_entry(entry)
        assert result["valid"] is False
        assert any("missing 'amount'" in e for e in result["errors"])


# ===========================================================================
# validate_tax (stub)
# ===========================================================================

class TestValidateTax:
    def test_stub_returns_valid(self):
        result = validate_tax({}, "ON", 0.13)
        assert result == {"valid": True, "errors": []}

    def test_stub_any_province(self):
        result = validate_tax({"lines": []}, "BC", 0.12)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_stub_zero_rate(self):
        result = validate_tax({}, "AB", 0.0)
        assert result == {"valid": True, "errors": []}


# ===========================================================================
# tools.py stubs
# ===========================================================================

class TestVendorHistoryLookup:
    def test_returns_empty_list(self):
        result = vendor_history_lookup("user-1", "Acme Corp")
        assert result == []

    def test_return_type(self):
        result = vendor_history_lookup("user-2", "Hardware Store")
        assert isinstance(result, list)


class TestCoaLookup:
    def test_returns_empty_list(self):
        result = coa_lookup("user-1")
        assert result == []

    def test_with_account_type_filter(self):
        result = coa_lookup("user-1", account_type="expense")
        assert result == []

    def test_return_type(self):
        assert isinstance(coa_lookup("user-1"), list)


class TestTaxRulesLookup:
    def test_returns_empty_dict(self):
        result = tax_rules_lookup("ON", "purchase")
        assert result == {}

    def test_return_type(self):
        assert isinstance(tax_rules_lookup("BC", "sale"), dict)
