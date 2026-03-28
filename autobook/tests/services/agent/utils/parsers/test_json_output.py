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
                    "resolution": "Cash payment",
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
                    "why_entry_differs": "Tax line amounts change",
                    "why_not_resolved": "No explicit mention in description",
                }
            ]
        })
        result = parse_json_output("disambiguator", raw)
        assert result is not None
        assert result["ambiguities"][0]["resolved"] is False


class TestDebitClassifierOutput:
    """parse_json_output for agent 'debit_classifier'."""

    def test_valid(self):
        raw = json.dumps({
            "reason": "Office supplies is an expense",
            "tuple": [0, 0, 1, 0, 0, 0],
        })
        result = parse_json_output("debit_classifier", raw)
        assert result is not None
        assert result["reason"] == "Office supplies is an expense"
        assert result["tuple"] == (0, 0, 1, 0, 0, 0)

    def test_missing_reason_fails(self):
        raw = json.dumps({"tuple": [0, 0, 1, 0, 0, 0]})
        result = parse_json_output("debit_classifier", raw)
        assert result is None

    def test_wrong_tuple_length_fails(self):
        raw = json.dumps({"reason": "test", "tuple": [1, 0, 1]})
        result = parse_json_output("debit_classifier", raw)
        assert result is None


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
    """parse_json_output for agent 'entry_builder'."""

    def test_valid_minimal(self):
        raw = json.dumps({
            "date": "2026-03-01",
            "description": "Office supplies purchase",
            "rationale": "Expense account for supplies",
            "lines": [
                {"account_name": "Office Supplies", "type": "debit", "amount": 100.0},
                {"account_name": "Cash", "type": "credit", "amount": 100.0},
            ],
        })
        result = parse_json_output("entry_builder", raw)
        assert result is not None
        assert len(result["lines"]) == 2
        assert result["date"] == "2026-03-01"

    def test_missing_lines_fails(self):
        raw = json.dumps({
            "date": "2026-03-01",
            "description": "test",
            "rationale": "test",
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
            "reason": "Cash is an asset decrease",
            "tuple": [0, 0, 0, 1, 0, 0],
        })
        result = parse_json_output("credit_classifier", raw)
        assert result is not None
        assert result["tuple"] == (0, 0, 0, 1, 0, 0)

    def test_debit_corrector_valid(self):
        raw = json.dumps({
            "reason": "Tuple was already correct",
            "tuple": [0, 0, 1, 0, 0, 0],
        })
        result = parse_json_output("debit_corrector", raw)
        assert result is not None

    def test_credit_corrector_valid(self):
        raw = json.dumps({
            "reason": "Fixed asset slot",
            "tuple": [0, 0, 0, 1, 0, 0],
        })
        result = parse_json_output("credit_corrector", raw)
        assert result is not None
