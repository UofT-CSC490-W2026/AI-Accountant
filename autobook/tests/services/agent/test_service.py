"""Tests for services/agent/service.py — execute, _build_initial_state, _extract_result."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from services.agent.graph.state import NOT_RUN, AGENT_NAMES
from services.agent.service import _build_initial_state, _extract_result, execute


class TestBuildInitialState:
    def test_sets_transaction_text_from_input_text(self):
        state = _build_initial_state({"input_text": "Pay rent $2000"})
        assert state["transaction_text"] == "Pay rent $2000"

    def test_falls_back_to_description(self):
        state = _build_initial_state({"description": "Pay rent $2000"})
        assert state["transaction_text"] == "Pay rent $2000"

    def test_defaults_to_empty(self):
        state = _build_initial_state({})
        assert state["transaction_text"] == ""

    def test_initializes_all_agent_fields(self):
        state = _build_initial_state({"input_text": "test"})
        for name in AGENT_NAMES:
            assert state[f"output_{name}"] == []
            assert state[f"status_{name}"] == NOT_RUN
            assert state[f"fix_context_{name}"] == []
            assert state[f"rag_cache_{name}"] == []

    def test_sets_ml_enrichment(self):
        state = _build_initial_state({
            "input_text": "test",
            "intent_label": "asset_purchase",
            "bank_category": "equipment",
            "entities": {"vendor": "Apple"},
        })
        assert state["ml_enrichment"]["intent_label"] == "asset_purchase"
        assert state["ml_enrichment"]["bank_category"] == "equipment"
        assert state["ml_enrichment"]["entities"]["vendor"] == "Apple"


class TestExtractResult:
    def test_extracts_entry_and_decision(self):
        entry = {
            "date": "2026-03-29",
            "description": "Record bank activity",
            "rationale": "Use the cash account for the settlement line.",
            "lines": [{"account_name": "Cash", "type": "debit", "amount": 100}],
        }
        final_state = {
            "iteration": 0,
            "output_entry_builder": [entry],
            "output_approver": [],
            "decision": "APPROVED",
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }
        result = _extract_result(final_state, {"parse_id": "p1", "transaction_id": "txn-1"})
        assert result["decision"] == "APPROVED"
        assert result["proposed_entry"]["entry"]["description"] == "Record bank activity"
        assert result["proposed_entry"]["lines"][0]["account_code"] == "1000"
        assert result["parse_id"] == "p1"
        assert result["clarification"]["required"] is False
        assert result["confidence"]["overall"] == 0.95
        assert result["explanation"] == "Use the cash account for the settlement line."

    def test_defaults_decision_to_approved(self):
        final_state = {
            "iteration": 0,
            "output_entry_builder": [None],
            "output_approver": [],
            "decision": None,
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }
        result = _extract_result(final_state, {})
        assert result["decision"] == "APPROVED"
        assert result["clarification"]["required"] is True
        assert result["confidence"]["overall"] == 0.0

    def test_extracts_clarification(self):
        final_state = {
            "iteration": 0,
            "output_entry_builder": [],
            "output_approver": [],
            "decision": "INCOMPLETE_INFORMATION",
            "clarification_questions": ["What was the purpose?"],
            "stuck_reason": None,
            "validation_error": None,
        }
        result = _extract_result(final_state, {})
        assert result["decision"] == "INCOMPLETE_INFORMATION"
        assert result["clarification_questions"] == ["What was the purpose?"]
        assert result["clarification"]["required"] is True
        assert result["confidence"]["overall"] == 0.0
        assert result["explanation"] == "Clarification required: What was the purpose?"

    def test_extracts_approver_confidence(self):
        final_state = {
            "iteration": 0,
            "output_entry_builder": [{
                "date": "2026-03-29",
                "description": "Record rent",
                "lines": [
                    {"account_name": "Rent Expense", "type": "debit", "amount": 2000},
                    {"account_name": "Cash", "type": "credit", "amount": 2000},
                ],
            }],
            "output_approver": [{"confidence": "VERY_CONFIDENT"}],
            "decision": "APPROVED",
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }
        result = _extract_result(final_state, {})
        assert result["approver_confidence"] == "VERY_CONFIDENT"
        assert result["confidence"]["overall"] == 0.99

    def test_no_entry_when_out_of_range(self):
        final_state = {
            "iteration": 5,
            "output_entry_builder": [],
            "output_approver": [],
            "decision": None,
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }
        result = _extract_result(final_state, {})
        assert result["proposed_entry"] is None
        assert result["clarification"]["required"] is True

    def test_requires_human_review_when_account_name_is_not_mapped(self):
        final_state = {
            "iteration": 0,
            "output_entry_builder": [{
                "date": "2026-03-29",
                "description": "Record custom asset",
                "lines": [{"account_name": "Custom Asset Bucket", "type": "debit", "amount": 100}],
            }],
            "output_approver": [{"confidence": "VERY_CONFIDENT"}],
            "decision": "APPROVED",
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }

        result = _extract_result(final_state, {})

        assert result["clarification"]["required"] is True
        assert result["confidence"]["overall"] == 0.0
        assert "could not be mapped to account codes" in result["explanation"]


class TestExecute:
    def test_invokes_graph_and_returns_result(self):
        entry = {
            "date": "2026-03-29",
            "description": "Rent payment",
            "lines": [
                {"account_name": "Rent Expense", "type": "debit", "amount": 2000},
                {"account_name": "Cash", "type": "credit", "amount": 2000},
            ],
        }
        final_state = {
            "iteration": 0,
            "output_entry_builder": [entry],
            "output_approver": [],
            "decision": "APPROVED",
            "clarification_questions": None,
            "stuck_reason": None,
            "validation_error": None,
        }
        with patch("services.agent.service.app") as mock_app:
            mock_app.invoke.return_value = final_state
            result = execute({"parse_id": "p1", "input_text": "Pay rent $2000"})

        assert result["decision"] == "APPROVED"
        assert result["proposed_entry"]["lines"][0]["account_code"] == "5200"
        assert result["clarification"]["required"] is False
        assert result["parse_id"] == "p1"
        mock_app.invoke.assert_called_once()
