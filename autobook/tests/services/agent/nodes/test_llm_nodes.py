"""Tests for LLM agent nodes — mock get_llm and RAG retrievers."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ── Stub external deps before imports ────────────────────────────────────

_lc_core = sys.modules.setdefault("langchain_core", ModuleType("langchain_core"))
_lc_msgs = sys.modules.setdefault("langchain_core.messages", ModuleType("langchain_core.messages"))
if not hasattr(_lc_msgs, "SystemMessage"):
    def _sys_init(self, content):
        self.content = content
        self.type = "system"
    def _hum_init(self, content):
        self.content = content
        self.type = "human"
    _lc_msgs.SystemMessage = type("SystemMessage", (), {"__init__": _sys_init})
    _lc_msgs.HumanMessage = type("HumanMessage", (), {"__init__": _hum_init})
_lc_core.messages = _lc_msgs
_lc_runnables = sys.modules.setdefault("langchain_core.runnables", ModuleType("langchain_core.runnables"))
_lc_runnables.RunnableConfig = dict
_lc_callbacks = sys.modules.setdefault("langchain_core.callbacks", ModuleType("langchain_core.callbacks"))
_lc_callbacks.BaseCallbackHandler = type("BaseCallbackHandler", (), {})
_lc_aws = sys.modules.setdefault("langchain_aws", ModuleType("langchain_aws"))
_lc_aws.ChatBedrockConverse = MagicMock()
_lg = sys.modules.setdefault("langgraph", ModuleType("langgraph"))
_lg_graph = sys.modules.setdefault("langgraph.graph", ModuleType("langgraph.graph"))
_lg_graph.StateGraph = MagicMock()
_lg_graph.END = "__end__"
_lg_types = sys.modules.setdefault("langgraph.types", ModuleType("langgraph.types"))
_lg_types.RetryPolicy = MagicMock()
_qc = sys.modules.setdefault("qdrant_client", ModuleType("qdrant_client"))
_qc.QdrantClient = MagicMock()
_qc_models = sys.modules.setdefault("qdrant_client.models", ModuleType("qdrant_client.models"))
_qc_models.Distance = MagicMock()
_qc_models.VectorParams = MagicMock()
_qc_models.PointStruct = MagicMock()
_qc_models.Filter = MagicMock()
_qc_models.FieldCondition = MagicMock()
_qc_models.MatchValue = MagicMock()
_qc.models = _qc_models
# Ensure boto3 is available for vectordb.embeddings — use real if installed, stub if not
if "boto3" not in sys.modules:
    try:
        import boto3  # noqa: F401
    except ImportError:
        _boto3 = ModuleType("boto3")
        _boto3.client = MagicMock(return_value=MagicMock())
        sys.modules["boto3"] = _boto3

from services.agent.graph.state import COMPLETE, NOT_RUN, AGENT_NAMES


def _make_state(transaction_text="Pay rent $2000", iteration=0):
    state = {
        "transaction_text": transaction_text,
        "user_context": {"province": "ON", "entity_type": "corporation"},
        "ml_enrichment": None,
        "iteration": iteration,
    }
    for name in AGENT_NAMES:
        state[f"output_{name}"] = []
        state[f"status_{name}"] = NOT_RUN
        state[f"fix_context_{name}"] = []
        state[f"rag_cache_{name}"] = []
    state["embedding_transaction"] = None
    state["embedding_error"] = None
    state["embedding_rejection"] = None
    state["decision"] = None
    state["validation_error"] = None
    state["clarification_questions"] = None
    state["stuck_reason"] = None
    return state


def _mock_llm_result(output_dict):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = output_dict
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = mock_result
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm


# ── Disambiguator ────────────────────────────────────────────────────────

class TestDisambiguatorNode:
    def test_no_ambiguity(self):
        from services.agent.nodes.disambiguator import disambiguator_node
        state = _make_state()
        llm = _mock_llm_result({"ambiguities": []})
        with patch("services.agent.nodes.disambiguator.get_llm", return_value=llm), \
             patch("services.agent.nodes.disambiguator.retrieve_transaction_examples", return_value=[]):
            result = disambiguator_node(state, {})
        assert result["status_disambiguator"] == COMPLETE
        assert "decision" not in result or result.get("decision") is None

    def test_unresolved_ambiguity_stored_in_output(self):
        from services.agent.nodes.disambiguator import disambiguator_node
        state = _make_state()
        output = {"ambiguities": [
            {"aspect": "purpose", "resolved": False, "clarification_question": "What was the purpose?",
             "options": ["A", "B"], "resolution": None}
        ]}
        llm = _mock_llm_result(output)
        with patch("services.agent.nodes.disambiguator.get_llm", return_value=llm), \
             patch("services.agent.nodes.disambiguator.retrieve_transaction_examples", return_value=[]):
            result = disambiguator_node(state, {})
        assert result["status_disambiguator"] == COMPLETE
        assert result["output_disambiguator"][0]["ambiguities"][0]["resolved"] is False

    def test_skip_when_complete(self):
        from services.agent.nodes.disambiguator import disambiguator_node
        state = _make_state()
        state["status_disambiguator"] = COMPLETE
        state["output_disambiguator"] = [{"ambiguities": []}]
        state["iteration"] = 1
        result = disambiguator_node(state, {})
        assert result["status_disambiguator"] == COMPLETE


# ── Debit Classifier ────────────────────────────────────────────────────

class TestDebitClassifierNode:
    def test_classifies(self):
        from services.agent.nodes.debit_classifier import debit_classifier_node
        state = _make_state()
        llm = _mock_llm_result({
            "asset_increase": [],
            "dividend_increase": [],
            "expense_increase": [{"reason": "expense", "category": "Occupancy expense", "count": 1}],
            "liability_decrease": [],
            "equity_decrease": [],
            "revenue_decrease": [],
        })
        with patch("services.agent.nodes.debit_classifier.get_llm", return_value=llm), \
             patch("services.agent.nodes.debit_classifier.retrieve_transaction_examples", return_value=[]):
            result = debit_classifier_node(state, {})
        assert result["status_debit_classifier"] == COMPLETE
        assert len(result["output_debit_classifier"]) == 1

    def test_skip_when_complete(self):
        from services.agent.nodes.debit_classifier import debit_classifier_node
        state = _make_state()
        state["status_debit_classifier"] = COMPLETE
        state["output_debit_classifier"] = [{"asset_increase": [{"reason": "asset", "category": "Office equipment", "count": 1}]}]
        state["iteration"] = 1
        result = debit_classifier_node(state, {})
        assert len(result["output_debit_classifier"]) == 2


# ── Credit Classifier ───────────────────────────────────────────────────

class TestCreditClassifierNode:
    def test_classifies(self):
        from services.agent.nodes.credit_classifier import credit_classifier_node
        state = _make_state()
        llm = _mock_llm_result({"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"})
        with patch("services.agent.nodes.credit_classifier.get_llm", return_value=llm), \
             patch("services.agent.nodes.credit_classifier.retrieve_transaction_examples", return_value=[]):
            result = credit_classifier_node(state, {})
        assert result["status_credit_classifier"] == COMPLETE


# ── Debit Corrector ──────────────────────────────────────────────────────

class TestDebitCorrectorNode:
    def test_corrects(self):
        from services.agent.nodes.debit_corrector import debit_corrector_node
        state = _make_state()
        state["output_debit_classifier"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_classifier"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        llm = _mock_llm_result({"tuple": (0, 0, 1, 0, 0, 0), "reason": "confirmed"})
        with patch("services.agent.nodes.debit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.debit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.debit_corrector.retrieve_correction_examples", return_value=[]):
            result = debit_corrector_node(state, {})
        assert result["status_debit_corrector"] == COMPLETE

    def test_uses_correction_examples_on_rerun(self):
        from services.agent.nodes.debit_corrector import debit_corrector_node
        state = _make_state()
        state["iteration"] = 1
        state["output_debit_classifier"] = [
            {"tuple": (0, 0, 1, 0, 0, 0), "reason": "v1"},
            {"tuple": (0, 0, 1, 0, 0, 0), "reason": "v2"},
        ]
        state["output_credit_classifier"] = [
            {"tuple": (0, 0, 0, 1, 0, 0), "reason": "v1"},
            {"tuple": (0, 0, 0, 1, 0, 0), "reason": "v2"},
        ]
        llm = _mock_llm_result({"tuple": (0, 0, 1, 0, 0, 0), "reason": "fixed"})
        correction_called = []
        with patch("services.agent.nodes.debit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.debit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.debit_corrector.retrieve_correction_examples",
                   side_effect=lambda s, k: correction_called.append(True) or []):
            result = debit_corrector_node(state, {})
        assert len(correction_called) == 1

    def test_skip_when_complete(self):
        """Lines 27-29: copy previous output for alignment when already COMPLETE."""
        from services.agent.nodes.debit_corrector import debit_corrector_node
        state = _make_state()
        prev_output = {"tuple": (0, 0, 1, 0, 0, 0), "reason": "confirmed"}
        state["status_debit_corrector"] = COMPLETE
        state["output_debit_corrector"] = [prev_output]
        state["iteration"] = 1
        result = debit_corrector_node(state, {})
        assert result["status_debit_corrector"] == COMPLETE
        assert len(result["output_debit_corrector"]) == 2
        assert result["output_debit_corrector"][1] is prev_output

    def test_no_correction_guard_reverts_to_input(self):
        """Lines 49-51: when reason says 'no correction' but tuple differs, revert."""
        from services.agent.nodes.debit_corrector import debit_corrector_node
        state = _make_state()
        # Input classifier says (0,0,1,0,0,0) — expense_increase = 1
        state["output_debit_classifier"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_classifier"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        # LLM says "no correction needed" but returns a DIFFERENT tuple via _count fields
        llm_output = {
            "reason": "No correction needed",
            "asset_increase_count": 1,
            "dividend_increase_count": 0,
            "expense_increase_count": 0,
            "liability_decrease_count": 0,
            "equity_decrease_count": 0,
            "revenue_decrease_count": 0,
        }
        llm = _mock_llm_result(llm_output)
        with patch("services.agent.nodes.debit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.debit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.debit_corrector.retrieve_correction_examples", return_value=[]):
            result = debit_corrector_node(state, {})
        output = result["output_debit_corrector"][0]
        # Guard should have reverted expense_increase_count to 1 (from input)
        assert output["expense_increase_count"] == 1
        assert output["asset_increase_count"] == 0
        # The final tuple should match the input
        assert output["tuple"] == [0, 0, 1, 0, 0, 0]


# ── Credit Corrector ─────────────────────────────────────────────────────

class TestCreditCorrectorNode:
    def test_corrects(self):
        from services.agent.nodes.credit_corrector import credit_corrector_node
        state = _make_state()
        state["output_debit_classifier"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_classifier"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        llm = _mock_llm_result({"tuple": (0, 0, 0, 1, 0, 0), "reason": "confirmed"})
        with patch("services.agent.nodes.credit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.credit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.credit_corrector.retrieve_correction_examples", return_value=[]):
            result = credit_corrector_node(state, {})
        assert result["status_credit_corrector"] == COMPLETE

    def test_skip_when_complete(self):
        """Lines 27-29: copy previous output for alignment when already COMPLETE."""
        from services.agent.nodes.credit_corrector import credit_corrector_node
        state = _make_state()
        prev_output = {"tuple": (0, 0, 0, 1, 0, 0), "reason": "confirmed"}
        state["status_credit_corrector"] = COMPLETE
        state["output_credit_corrector"] = [prev_output]
        state["iteration"] = 1
        result = credit_corrector_node(state, {})
        assert result["status_credit_corrector"] == COMPLETE
        assert len(result["output_credit_corrector"]) == 2
        assert result["output_credit_corrector"][1] is prev_output

    def test_uses_correction_examples_on_rerun(self):
        """Line 36: on iteration > 0, retrieve_correction_examples is used."""
        from services.agent.nodes.credit_corrector import credit_corrector_node
        state = _make_state()
        state["iteration"] = 1
        state["output_debit_classifier"] = [
            {"tuple": (0, 0, 1, 0, 0, 0), "reason": "v1"},
            {"tuple": (0, 0, 1, 0, 0, 0), "reason": "v2"},
        ]
        state["output_credit_classifier"] = [
            {"tuple": (0, 0, 0, 1, 0, 0), "reason": "v1"},
            {"tuple": (0, 0, 0, 1, 0, 0), "reason": "v2"},
        ]
        llm = _mock_llm_result({"tuple": (0, 0, 0, 1, 0, 0), "reason": "fixed"})
        correction_called = []
        with patch("services.agent.nodes.credit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.credit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.credit_corrector.retrieve_correction_examples",
                   side_effect=lambda s, k: correction_called.append(True) or []):
            result = credit_corrector_node(state, {})
        assert len(correction_called) == 1

    def test_no_correction_guard_reverts_to_input(self):
        """Lines 49-51: when reason says 'no correction' but tuple differs, revert."""
        from services.agent.nodes.credit_corrector import credit_corrector_node
        state = _make_state()
        # Input classifier says (0,0,0,1,0,0) — asset_decrease = 1
        state["output_debit_classifier"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_classifier"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        # LLM says "no correction needed" but returns a DIFFERENT tuple via _count fields
        llm_output = {
            "reason": "No correction needed",
            "liability_increase_count": 1,
            "equity_increase_count": 0,
            "revenue_increase_count": 0,
            "asset_decrease_count": 0,
            "dividend_decrease_count": 0,
            "expense_decrease_count": 0,
        }
        llm = _mock_llm_result(llm_output)
        with patch("services.agent.nodes.credit_corrector.get_llm", return_value=llm), \
             patch("services.agent.nodes.credit_corrector.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.credit_corrector.retrieve_correction_examples", return_value=[]):
            result = credit_corrector_node(state, {})
        output = result["output_credit_corrector"][0]
        # Guard should have reverted asset_decrease_count to 1 (from input)
        assert output["asset_decrease_count"] == 1
        assert output["liability_increase_count"] == 0
        # The final tuple should match the input
        assert output["tuple"] == [0, 0, 0, 1, 0, 0]


# ── Entry Builder ────────────────────────────────────────────────────────

class TestEntryBuilderNode:
    def test_builds_entry(self):
        from services.agent.nodes.entry_builder import entry_builder_node
        state = _make_state()
        state["output_debit_corrector"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_corrector"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        entry = {"date": "2026-03-27", "description": "Rent", "rationale": "test",
                 "lines": [{"account_name": "Rent", "type": "debit", "amount": 2000},
                           {"account_name": "Cash", "type": "credit", "amount": 2000}]}
        llm = _mock_llm_result(entry)
        with patch("services.agent.nodes.entry_builder.get_llm", return_value=llm), \
             patch("services.agent.nodes.entry_builder.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.entry_builder.coa_lookup", return_value=[]), \
             patch("services.agent.nodes.entry_builder.tax_rules_lookup", return_value={}), \
             patch("services.agent.nodes.entry_builder.vendor_history_lookup", return_value=[]):
            result = entry_builder_node(state, {"configurable": {}})
        assert result["status_entry_builder"] == COMPLETE
        assert result["output_entry_builder"][0]["lines"] is not None

    def test_skip_when_complete(self):
        from services.agent.nodes.entry_builder import entry_builder_node
        state = _make_state()
        state["status_entry_builder"] = COMPLETE
        state["output_entry_builder"] = [{"lines": [], "reason": "prev"}]
        state["iteration"] = 1
        result = entry_builder_node(state, {"configurable": {}})
        assert result["status_entry_builder"] == COMPLETE
        assert len(result["output_entry_builder"]) == 2

    def test_incomplete_information_propagated(self):
        from services.agent.nodes.entry_builder import entry_builder_node
        state = _make_state()
        state["output_debit_corrector"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_corrector"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        entry = {"reason": "test", "decision": "INCOMPLETE_INFORMATION",
                 "clarification_questions": ["Is HST included?"],
                 "lines": [{"account_name": "Rent", "type": "debit", "amount": 2000},
                           {"account_name": "Cash", "type": "credit", "amount": 2000}]}
        llm = _mock_llm_result(entry)
        with patch("services.agent.nodes.entry_builder.get_llm", return_value=llm), \
             patch("services.agent.nodes.entry_builder.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.entry_builder.coa_lookup", return_value=[]), \
             patch("services.agent.nodes.entry_builder.tax_rules_lookup", return_value={}), \
             patch("services.agent.nodes.entry_builder.vendor_history_lookup", return_value=[]):
            result = entry_builder_node(state, {"configurable": {}})
        assert result["decision"] == "INCOMPLETE_INFORMATION"
        assert result["clarification_questions"] == ["Is HST included?"]

    def test_terminal_decision_when_evaluation_off(self):
        from services.agent.nodes.entry_builder import entry_builder_node
        state = _make_state()
        state["output_debit_corrector"] = [{"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"}]
        state["output_credit_corrector"] = [{"tuple": (0, 0, 0, 1, 0, 0), "reason": "asset decrease"}]
        entry = {"reason": "test", "decision": "STUCK", "stuck_reason": "cannot resolve",
                 "lines": [{"account_name": "Rent", "type": "debit", "amount": 2000},
                           {"account_name": "Cash", "type": "credit", "amount": 2000}]}
        llm = _mock_llm_result(entry)
        with patch("services.agent.nodes.entry_builder.get_llm", return_value=llm), \
             patch("services.agent.nodes.entry_builder.retrieve_transaction_examples", return_value=[]), \
             patch("services.agent.nodes.entry_builder.coa_lookup", return_value=[]), \
             patch("services.agent.nodes.entry_builder.tax_rules_lookup", return_value={}), \
             patch("services.agent.nodes.entry_builder.vendor_history_lookup", return_value=[]):
            result = entry_builder_node(state, {"configurable": {"evaluation_active": False}})
        assert result["decision"] == "STUCK"
        assert result["stuck_reason"] == "cannot resolve"


# ── Approver ─────────────────────────────────────────────────────────────

class TestApproverNode:
    def test_approves(self):
        from services.agent.nodes.approver import approver_node
        state = _make_state()
        state["output_entry_builder"] = [{"lines": []}]
        llm = _mock_llm_result({"decision": "APPROVED", "confidence": "VERY_CONFIDENT", "reason": "correct"})
        with patch("services.agent.nodes.approver.get_llm", return_value=llm), \
             patch("services.agent.nodes.approver.retrieve_transaction_examples", return_value=[]):
            result = approver_node(state, {})
        assert result.get("decision") == "APPROVED"

    def test_stuck(self):
        from services.agent.nodes.approver import approver_node
        state = _make_state()
        state["output_entry_builder"] = [{"lines": []}]
        llm = _mock_llm_result({"decision": "STUCK", "confidence": "VERY_UNCERTAIN", "reason": "unclear"})
        with patch("services.agent.nodes.approver.get_llm", return_value=llm), \
             patch("services.agent.nodes.approver.retrieve_transaction_examples", return_value=[]):
            result = approver_node(state, {})
        assert result["decision"] == "STUCK"
        assert result["stuck_reason"] == "unclear"

    def test_rejected_no_decision(self):
        from services.agent.nodes.approver import approver_node
        state = _make_state()
        state["output_entry_builder"] = [{"lines": []}]
        llm = _mock_llm_result({"decision": "REJECTED", "confidence": "SOMEWHAT_CONFIDENT", "reason": "wrong account"})
        with patch("services.agent.nodes.approver.get_llm", return_value=llm), \
             patch("services.agent.nodes.approver.retrieve_transaction_examples", return_value=[]):
            result = approver_node(state, {})
        assert "decision" not in result or result.get("decision") is None


# ── Diagnostician ────────────────────────────────────────────────────────

class TestDiagnosticianNode:
    def test_fix(self):
        from services.agent.nodes.diagnostician import diagnostician_node
        state = _make_state()
        state["output_approver"] = [{"decision": "REJECTED", "reason": "wrong"}]
        llm = _mock_llm_result({"decision": "FIX", "fix_plans": [{"agent": 1, "fix_context": "fix debit"}]})
        with patch("services.agent.nodes.diagnostician.get_llm", return_value=llm), \
             patch("services.agent.nodes.diagnostician.retrieve_fix_history", return_value=[]):
            result = diagnostician_node(state, {})
        assert result["status_diagnostician"] == COMPLETE
        assert "decision" not in result or result.get("decision") is None

    def test_stuck(self):
        from services.agent.nodes.diagnostician import diagnostician_node
        state = _make_state()
        state["output_approver"] = [{"decision": "REJECTED", "reason": "unclear"}]
        llm = _mock_llm_result({"decision": "STUCK", "fix_plans": [], "stuck_reason": "cannot resolve"})
        with patch("services.agent.nodes.diagnostician.get_llm", return_value=llm), \
             patch("services.agent.nodes.diagnostician.retrieve_fix_history", return_value=[]):
            result = diagnostician_node(state, {})
        assert result["decision"] == "STUCK"
        assert result["stuck_reason"] == "cannot resolve"
