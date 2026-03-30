from __future__ import annotations

import json

from services.agent.utils.parsers.json_output import parse_json_output


class TestDisambiguatorOutput:
    """parse_json_output for agent 'disambiguator'."""

    def test_valid_with_resolved_ambiguity(self):
        raw = json.dumps({
            "ambiguities": [
                {
                    "aspect": "payment method",
                    "resolved": True,
                }
            ]
        })
        result = parse_json_output("disambiguator", raw)
        assert result is not None
        assert len(result["ambiguities"]) == 1
        assert result["ambiguities"][0]["resolved"] is True

    def test_valid_empty_ambiguities(self):
        raw = json.dumps({"ambiguities": []})
        result = parse_json_output("disambiguator", raw)
        assert result is not None
        assert result["ambiguities"] == []

    def test_valid_unresolved_ambiguity(self):
        raw = json.dumps({
            "ambiguities": [
                {
                    "aspect": "tax treatment",
                    "resolved": False,
                    "options": ["HST included", "HST excluded"],
                    "clarification_question": "Is HST included?",
                    "why_entry_depends_on_clarification": "Tax line amounts change",
                    "why_ambiguity_not_resolved_by_given_info": "No explicit mention",
                }
            ]
        })
        result = parse_json_output("disambiguator", raw)
        assert result is not None
        assert result["ambiguities"][0]["resolved"] is False


class TestDebitClassifierOutput:
    """parse_json_output for agent 'debit_classifier' — V3 per-slot list format."""

    def test_valid(self):
        raw = json.dumps({
            "asset_increase": [],
            "dividend_increase": [],
            "expense_increase": [
                {"reason": "Office supplies is an expense",
                 "category": "Advertising expense",
                 "count": 1}
            ],
            "liability_decrease": [],
            "equity_decrease": [],
            "revenue_decrease": [],
        })
        result = parse_json_output("debit_classifier", raw)
        assert result is not None
        assert len(result["expense_increase"]) == 1
        assert result["expense_increase"][0]["count"] == 1

    def test_empty_slots_valid(self):
        raw = json.dumps({
            "asset_increase": [],
            "dividend_increase": [],
            "expense_increase": [],
            "liability_decrease": [],
            "equity_decrease": [],
            "revenue_decrease": [],
        })
        result = parse_json_output("debit_classifier", raw)
        assert result is not None

    def test_defaults_fill_missing_slots(self):
        """Missing slots get default empty lists via Pydantic defaults."""
        raw = json.dumps({
            "expense_increase": [
                {"reason": "test", "category": "Advertising expense", "count": 1}
            ],
        })
        result = parse_json_output("debit_classifier", raw)
        assert result is not None
        assert result["asset_increase"] == []


class TestApproverOutput:
    """parse_json_output for agent 'approver'."""

    def test_valid_approved(self):
        raw = json.dumps({
            "reason": "All checks passed",
            "decision": "APPROVED",
            "confidence": "VERY_CONFIDENT",
        })
        result = parse_json_output("approver", raw)
        assert result is not None
        assert result["decision"] == "APPROVED"
        assert result["confidence"] == "VERY_CONFIDENT"

    def test_invalid_decision_value(self):
        raw = json.dumps({
            "reason": "ok",
            "decision": "MAYBE",
            "confidence": "VERY_CONFIDENT",
        })
        result = parse_json_output("approver", raw)
        assert result is None

    def test_invalid_confidence_value(self):
        raw = json.dumps({
            "reason": "ok",
            "decision": "APPROVED",
            "confidence": "KINDA_SURE",
        })
        result = parse_json_output("approver", raw)
        assert result is None


class TestEntryBuilderOutput:
    """parse_json_output for agent 'entry_builder' — V3 EntryDrafterOutput format."""

    def test_valid_minimal(self):
        raw = json.dumps({
            "reason": "Rent is operating expense",
            "lines": [
                {"account_name": "Rent Expense", "type": "debit", "amount": 2000.0},
                {"account_name": "Cash", "type": "credit", "amount": 2000.0},
            ],
        })
        result = parse_json_output("entry_builder", raw)
        assert result is not None
        assert len(result["lines"]) == 2

    def test_missing_lines_fails(self):
        raw = json.dumps({
            "reason": "test",
        })
        result = parse_json_output("entry_builder", raw)
        assert result is None


class TestDiagnosticianOutput:
    """parse_json_output for agent 'diagnostician'."""

    def test_valid_fix(self):
        raw = json.dumps({
            "reasoning": "Debit classifier misclassified",
            "decision": "FIX",
            "fix_plans": [{"agent": 1, "fix_context": "Reclassify as liability"}],
        })
        result = parse_json_output("diagnostician", raw)
        assert result is not None
        assert result["decision"] == "FIX"
        assert len(result["fix_plans"]) == 1

    def test_valid_stuck(self):
        raw = json.dumps({
            "reasoning": "Cannot determine correct entry",
            "decision": "STUCK",
            "fix_plans": [],
            "stuck_reason": "Insufficient information",
        })
        result = parse_json_output("diagnostician", raw)
        assert result is not None
        assert result["decision"] == "STUCK"


class TestEdgeCases:
    """Cross-cutting edge cases."""

    def test_invalid_json_returns_none(self):
        result = parse_json_output("disambiguator", "not json at all")
        assert result is None

    def test_markdown_fences_stripped(self):
        inner = json.dumps({"ambiguities": []})
        raw = f"```json\n{inner}\n```"
        result = parse_json_output("disambiguator", raw)
        assert result is not None
        assert result["ambiguities"] == []

    def test_markdown_fences_no_language(self):
        inner = json.dumps({"ambiguities": []})
        raw = f"```\n{inner}\n```"
        result = parse_json_output("disambiguator", raw)
        assert result is not None

    def test_unknown_agent_returns_none(self):
        raw = json.dumps({"foo": "bar"})
        result = parse_json_output("unknown_agent", raw)
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_json_output("disambiguator", "")
        assert result is None

    def test_credit_classifier_valid(self):
        raw = json.dumps({
            "liability_increase": [],
            "equity_increase": [],
            "revenue_increase": [],
            "asset_decrease": [
                {"reason": "Cash is an asset decrease",
                 "category": "Cash and cash equivalents",
                 "count": 1}
            ],
            "dividend_decrease": [],
            "expense_decrease": [],
        })
        result = parse_json_output("credit_classifier", raw)
        assert result is not None
        assert len(result["asset_decrease"]) == 1

    def test_debit_corrector_valid(self):
        raw = json.dumps({
            "reason": "Tuple was already correct",
            "asset_increase_reason": "No change needed",
            "asset_increase_count": 0,
            "dividend_increase_reason": "",
            "dividend_increase_count": 0,
            "expense_increase_reason": "Confirmed as expense",
            "expense_increase_count": 1,
            "liability_decrease_reason": "",
            "liability_decrease_count": 0,
            "equity_decrease_reason": "",
            "equity_decrease_count": 0,
            "revenue_decrease_reason": "",
            "revenue_decrease_count": 0,
        })
        result = parse_json_output("debit_corrector", raw)
        assert result is not None

    def test_credit_corrector_valid(self):
        raw = json.dumps({
            "reason": "Fixed asset slot",
            "liability_increase_reason": "",
            "liability_increase_count": 0,
            "equity_increase_reason": "",
            "equity_increase_count": 0,
            "revenue_increase_reason": "",
            "revenue_increase_count": 0,
            "asset_decrease_reason": "Cash decreases",
            "asset_decrease_count": 1,
            "dividend_decrease_reason": "",
            "dividend_decrease_count": 0,
            "expense_decrease_reason": "",
            "expense_decrease_count": 0,
        })
        result = parse_json_output("credit_corrector", raw)
        assert result is not None
