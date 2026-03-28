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
        llm = _mock_llm_result({"tuple": (0, 0, 1, 0, 0, 0), "reason": "expense"})
        with patch("services.agent.nodes.debit_classifier.get_llm", return_value=llm), \
             patch("services.agent.nodes.debit_classifier.retrieve_transaction_examples", return_value=[]):
            result = debit_classifier_node(state, {})
        assert result["status_debit_classifier"] == COMPLETE
        assert result["output_debit_classifier"][0]["tuple"] == (0, 0, 1, 0, 0, 0)

    def test_skip_when_complete(self):
        from services.agent.nodes.debit_classifier import debit_classifier_node
        state = _make_state()
        state["status_debit_classifier"] = COMPLETE
        state["output_debit_classifier"] = [{"tuple": (1, 0, 0, 0, 0, 0), "reason": "asset"}]
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
