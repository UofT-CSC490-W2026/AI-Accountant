"""Tests for V3 agent nodes — ambiguity_detector, complexity_detector,
tax_specialist, decision_maker, entry_drafter, and merge_lines.

Stubs langchain_core, langchain_aws, langgraph in sys.modules before imports,
following the same pattern as test_llm_nodes.py.
"""
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
    def _hum_init(self, content=None, **kwargs):
        self.content = content or kwargs.get("content")
        self.type = "human"
    def _ai_init(self, content=None, **kwargs):
        self.content = content or kwargs.get("content")
        self.type = "ai"
        self.tool_calls = kwargs.get("tool_calls", [])
    def _tool_init(self, content=None, **kwargs):
        self.content = content or kwargs.get("content")
        self.type = "tool"
        self.tool_call_id = kwargs.get("tool_call_id")
    _lc_msgs.SystemMessage = type("SystemMessage", (), {"__init__": _sys_init})
    _lc_msgs.HumanMessage = type("HumanMessage", (), {"__init__": _hum_init})
    _lc_msgs.AIMessage = type("AIMessage", (), {"__init__": _ai_init})
    _lc_msgs.ToolMessage = type("ToolMessage", (), {"__init__": _tool_init})
_lc_core.messages = _lc_msgs

_lc_runnables = sys.modules.setdefault("langchain_core.runnables", ModuleType("langchain_core.runnables"))
_lc_runnables.RunnableConfig = dict
_lc_callbacks = sys.modules.setdefault("langchain_core.callbacks", ModuleType("langchain_core.callbacks"))
_lc_callbacks.BaseCallbackHandler = type("BaseCallbackHandler", (), {})

# Stub langchain_core.tools — needed for calculator.py's @tool decorator
_lc_tools = sys.modules.setdefault("langchain_core.tools", ModuleType("langchain_core.tools"))
if not hasattr(_lc_tools, "tool"):
    _lc_tools.tool = lambda f: f  # no-op decorator

_lc_aws = sys.modules.setdefault("langchain_aws", ModuleType("langchain_aws"))
_lc_aws.ChatBedrockConverse = MagicMock()
_lg = sys.modules.setdefault("langgraph", ModuleType("langgraph"))
_lg_graph = sys.modules.setdefault("langgraph.graph", ModuleType("langgraph.graph"))
_lg_graph.StateGraph = MagicMock()
_lg_graph.END = "__end__"
_lg_types = sys.modules.setdefault("langgraph.types", ModuleType("langgraph.types"))
_lg_types.RetryPolicy = MagicMock()

from services.agent.graph.state import COMPLETE, NOT_RUN, AGENT_NAMES


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_state(transaction_text="Pay rent $2000", iteration=0):
    """Build a minimal PipelineState dict for testing."""
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


# ── Ambiguity Detector ───────────────────────────────────────────────────

class TestAmbiguityDetectorNode:
    """Tests for ambiguity_detector_node."""

    def test_no_ambiguity(self):
        """Normal execution with no ambiguities found."""
        from services.agent.nodes.ambiguity_detector import ambiguity_detector_node

        state = _make_state()
        output = {"ambiguities": []}
        with patch("services.agent.nodes.ambiguity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.ambiguity_detector.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.ambiguity_detector.retrieve_transaction_examples", return_value=[]):
            result = ambiguity_detector_node(state, {})

        assert result["status_ambiguity_detector"] == COMPLETE
        assert result["status_disambiguator"] == COMPLETE  # legacy alias
        assert result["output_ambiguity_detector"] == [{"ambiguities": []}]
        assert result["output_disambiguator"] == [{"ambiguities": []}]

    def test_unresolved_ambiguity(self):
        """Unresolved ambiguities are stored in output."""
        from services.agent.nodes.ambiguity_detector import ambiguity_detector_node

        state = _make_state()
        output = {"ambiguities": [
            {"aspect": "purpose", "resolved": False,
             "clarification_question": "What was the purpose?",
             "options": ["Capital expenditure", "Expense"],
             "why_entry_depends_on_clarification": "Different accounts",
             "why_ambiguity_not_resolved_by_given_info": "Text does not specify"},
        ]}
        with patch("services.agent.nodes.ambiguity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.ambiguity_detector.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.ambiguity_detector.retrieve_transaction_examples", return_value=[]):
            result = ambiguity_detector_node(state, {})

        assert result["status_ambiguity_detector"] == COMPLETE
        assert len(result["output_ambiguity_detector"]) == 1
        assert result["output_ambiguity_detector"][0]["ambiguities"][0]["resolved"] is False
        assert result["output_ambiguity_detector"][0]["ambiguities"][0]["aspect"] == "purpose"

    def test_resolved_ambiguity(self):
        """Resolved ambiguity passes through cleanly."""
        from services.agent.nodes.ambiguity_detector import ambiguity_detector_node

        state = _make_state()
        output = {"ambiguities": [
            {"aspect": "GST treatment", "resolved": True,
             "clarification_question": None, "options": None,
             "why_entry_depends_on_clarification": None,
             "why_ambiguity_not_resolved_by_given_info": None},
        ]}
        with patch("services.agent.nodes.ambiguity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.ambiguity_detector.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.ambiguity_detector.retrieve_transaction_examples", return_value=[]):
            result = ambiguity_detector_node(state, {})

        assert result["status_ambiguity_detector"] == COMPLETE
        assert result["output_ambiguity_detector"][0]["ambiguities"][0]["resolved"] is True

    def test_skip_when_complete(self):
        """Copies previous output on re-entry when status is COMPLETE."""
        from services.agent.nodes.ambiguity_detector import ambiguity_detector_node

        state = _make_state(iteration=1)
        state["status_ambiguity_detector"] = COMPLETE
        state["output_ambiguity_detector"] = [{"ambiguities": []}]

        result = ambiguity_detector_node(state, {})

        assert result["status_ambiguity_detector"] == COMPLETE
        assert len(result["output_ambiguity_detector"]) == 2
        assert result["output_ambiguity_detector"][1] == {"ambiguities": []}

    def test_history_appended_not_replaced(self):
        """Multiple iterations accumulate in the history list."""
        from services.agent.nodes.ambiguity_detector import ambiguity_detector_node

        state = _make_state(iteration=1)
        state["output_ambiguity_detector"] = [{"ambiguities": [{"aspect": "v0", "resolved": True}]}]
        output_v1 = {"ambiguities": [{"aspect": "v1", "resolved": False}]}

        with patch("services.agent.nodes.ambiguity_detector.invoke_structured", return_value=output_v1), \
             patch("services.agent.nodes.ambiguity_detector.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.ambiguity_detector.retrieve_transaction_examples", return_value=[]):
            result = ambiguity_detector_node(state, {})

        assert len(result["output_ambiguity_detector"]) == 2
        assert result["output_ambiguity_detector"][0]["ambiguities"][0]["aspect"] == "v0"
        assert result["output_ambiguity_detector"][1]["ambiguities"][0]["aspect"] == "v1"


# ── Complexity Detector ──────────────────────────────────────────────────

class TestComplexityDetectorNode:
    """Tests for complexity_detector_node."""

    def test_no_flags(self):
        """No complexity flags returned."""
        from services.agent.nodes.complexity_detector import complexity_detector_node

        state = _make_state()
        output = {"flags": []}
        with patch("services.agent.nodes.complexity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.complexity_detector.get_llm", return_value=MagicMock()):
            result = complexity_detector_node(state, {})

        assert result["status_complexity_detector"] == COMPLETE
        assert result["output_complexity_detector"] == [{"flags": []}]

    def test_skeptical_flag(self):
        """Complexity flag with skeptical=True is captured."""
        from services.agent.nodes.complexity_detector import complexity_detector_node

        state = _make_state()
        output = {"flags": [
            {"aspect": "lease accounting", "skeptical": True,
             "why_llm_cannot_do_this": "Requires IFRS 16 amortization schedule",
             "what_is_best_llm_can_do": "Simple rent expense entry"},
        ]}
        with patch("services.agent.nodes.complexity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.complexity_detector.get_llm", return_value=MagicMock()):
            result = complexity_detector_node(state, {})

        assert result["status_complexity_detector"] == COMPLETE
        assert result["output_complexity_detector"][0]["flags"][0]["skeptical"] is True

    def test_non_skeptical_flag(self):
        """Complexity flag with skeptical=False is captured."""
        from services.agent.nodes.complexity_detector import complexity_detector_node

        state = _make_state()
        output = {"flags": [
            {"aspect": "basic expense", "skeptical": False,
             "why_llm_cannot_do_this": None,
             "what_is_best_llm_can_do": None},
        ]}
        with patch("services.agent.nodes.complexity_detector.invoke_structured", return_value=output), \
             patch("services.agent.nodes.complexity_detector.get_llm", return_value=MagicMock()):
            result = complexity_detector_node(state, {})

        assert result["output_complexity_detector"][0]["flags"][0]["skeptical"] is False

    def test_skip_when_complete(self):
        """Copies previous output when status is COMPLETE."""
        from services.agent.nodes.complexity_detector import complexity_detector_node

        state = _make_state(iteration=1)
        state["status_complexity_detector"] = COMPLETE
        state["output_complexity_detector"] = [{"flags": []}]

        result = complexity_detector_node(state, {})

        assert result["status_complexity_detector"] == COMPLETE
        assert len(result["output_complexity_detector"]) == 2

    def test_history_appended(self):
        """History accumulates across iterations."""
        from services.agent.nodes.complexity_detector import complexity_detector_node

        state = _make_state(iteration=1)
        state["output_complexity_detector"] = [{"flags": [{"aspect": "v0", "skeptical": False}]}]
        output_v1 = {"flags": [{"aspect": "v1", "skeptical": True}]}

        with patch("services.agent.nodes.complexity_detector.invoke_structured", return_value=output_v1), \
             patch("services.agent.nodes.complexity_detector.get_llm", return_value=MagicMock()):
            result = complexity_detector_node(state, {})

        assert len(result["output_complexity_detector"]) == 2


# ── Tax Specialist ───────────────────────────────────────────────────────

class TestTaxSpecialistNode:
    """Tests for tax_specialist_node."""

    def test_taxable_transaction(self):
        """Taxable transaction with rate and amount."""
        from services.agent.nodes.tax_specialist import tax_specialist_node

        state = _make_state()
        output = {
            "reasoning": "HST applies at 13%",
            "tax_mentioned": True,
            "taxable": True,
            "add_tax_lines": True,
            "tax_rate": 0.13,
            "tax_amount": 260.0,
            "treatment": "recoverable",
        }
        with patch("services.agent.nodes.tax_specialist.invoke_structured", return_value=output), \
             patch("services.agent.nodes.tax_specialist.get_llm", return_value=MagicMock()):
            result = tax_specialist_node(state, {})

        assert result["status_tax_specialist"] == COMPLETE
        assert result["output_tax_specialist"][0]["taxable"] is True
        assert result["output_tax_specialist"][0]["tax_rate"] == 0.13
        assert result["output_tax_specialist"][0]["treatment"] == "recoverable"

    def test_non_taxable_transaction(self):
        """Non-taxable transaction (e.g. salary)."""
        from services.agent.nodes.tax_specialist import tax_specialist_node

        state = _make_state(transaction_text="Pay salary $5000")
        output = {
            "reasoning": "Salaries are not subject to sales tax",
            "tax_mentioned": False,
            "taxable": False,
            "add_tax_lines": False,
            "tax_rate": None,
            "tax_amount": None,
            "treatment": "not_applicable",
        }
        with patch("services.agent.nodes.tax_specialist.invoke_structured", return_value=output), \
             patch("services.agent.nodes.tax_specialist.get_llm", return_value=MagicMock()):
            result = tax_specialist_node(state, {})

        assert result["status_tax_specialist"] == COMPLETE
        assert result["output_tax_specialist"][0]["taxable"] is False
        assert result["output_tax_specialist"][0]["treatment"] == "not_applicable"

    def test_non_recoverable_tax(self):
        """Tax is non-recoverable (e.g. meals entertainment)."""
        from services.agent.nodes.tax_specialist import tax_specialist_node

        state = _make_state(transaction_text="Client dinner $500 plus HST")
        output = {
            "reasoning": "50% of meal tax is non-recoverable",
            "tax_mentioned": True,
            "taxable": True,
            "add_tax_lines": True,
            "tax_rate": 0.13,
            "tax_amount": 65.0,
            "treatment": "non_recoverable",
        }
        with patch("services.agent.nodes.tax_specialist.invoke_structured", return_value=output), \
             patch("services.agent.nodes.tax_specialist.get_llm", return_value=MagicMock()):
            result = tax_specialist_node(state, {})

        assert result["output_tax_specialist"][0]["treatment"] == "non_recoverable"

    def test_skip_when_complete(self):
        """Copies previous output when status is COMPLETE."""
        from services.agent.nodes.tax_specialist import tax_specialist_node

        state = _make_state(iteration=1)
        state["status_tax_specialist"] = COMPLETE
        prev_output = {"reasoning": "prev", "tax_mentioned": False, "taxable": False,
                       "add_tax_lines": False, "tax_rate": None, "tax_amount": None,
                       "treatment": "not_applicable"}
        state["output_tax_specialist"] = [prev_output]

        result = tax_specialist_node(state, {})

        assert result["status_tax_specialist"] == COMPLETE
        assert len(result["output_tax_specialist"]) == 2
        assert result["output_tax_specialist"][1] == prev_output


# ── Decision Maker ───────────────────────────────────────────────────────

class TestDecisionMakerNode:
    """Tests for decision_maker_node."""

    def test_proceed(self):
        """Decision is proceed — no pipeline-level decision set."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "No blocking ambiguities",
            "missing_info_decision": False,
            "clarification_questions": [],
            "complexity_assessment": "Straightforward",
            "llm_stuck": False,
            "stuck_reason": None,
            "classification_assessment": "Debit and credit look correct",
            "debit_approved": True,
            "override_debit": None,
            "credit_approved": True,
            "override_credit": None,
            "decision_rationale": "All clear",
            "decision": "proceed",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["status_decision_maker"] == COMPLETE
        assert result["output_decision_maker"][0]["decision"] == "proceed"
        # No pipeline decision set for "proceed"
        assert "decision" not in result or result.get("decision") is None

    def test_missing_info(self):
        """Decision is missing_info — sets INCOMPLETE_INFORMATION and clarification questions."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "Missing purpose info",
            "missing_info_decision": True,
            "clarification_questions": ["Is this a capital expenditure?"],
            "complexity_assessment": "N/A",
            "llm_stuck": False,
            "stuck_reason": None,
            "classification_assessment": "Cannot classify without clarity",
            "debit_approved": True,
            "override_debit": None,
            "credit_approved": True,
            "override_credit": None,
            "decision_rationale": "Need more info",
            "decision": "missing_info",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["status_decision_maker"] == COMPLETE
        assert result["decision"] == "INCOMPLETE_INFORMATION"
        assert result["clarification_questions"] == ["Is this a capital expenditure?"]

    def test_missing_info_no_questions(self):
        """Decision is missing_info but no clarification questions provided."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "Missing info",
            "missing_info_decision": True,
            "clarification_questions": [],
            "complexity_assessment": "N/A",
            "llm_stuck": False,
            "stuck_reason": None,
            "classification_assessment": "N/A",
            "debit_approved": True,
            "override_debit": None,
            "credit_approved": True,
            "override_credit": None,
            "decision_rationale": "Need info",
            "decision": "missing_info",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["decision"] == "INCOMPLETE_INFORMATION"
        # Empty list is falsy, so clarification_questions should NOT be set
        assert "clarification_questions" not in result

    def test_llm_stuck(self):
        """Decision is llm_stuck — sets STUCK and stuck_reason."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "N/A",
            "missing_info_decision": False,
            "clarification_questions": [],
            "complexity_assessment": "IFRS 16 lease requires amortization schedule",
            "llm_stuck": True,
            "stuck_reason": "Cannot compute amortization",
            "classification_assessment": "N/A",
            "debit_approved": True,
            "override_debit": None,
            "credit_approved": True,
            "override_credit": None,
            "decision_rationale": "LLM lacks lease accounting capability",
            "decision": "llm_stuck",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["status_decision_maker"] == COMPLETE
        assert result["decision"] == "STUCK"
        assert result["stuck_reason"] == "Cannot compute amortization"

    def test_llm_stuck_no_reason(self):
        """Decision is llm_stuck but no stuck_reason provided."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "N/A",
            "missing_info_decision": False,
            "clarification_questions": [],
            "complexity_assessment": "Too complex",
            "llm_stuck": True,
            "stuck_reason": None,
            "classification_assessment": "N/A",
            "debit_approved": True,
            "override_debit": None,
            "credit_approved": True,
            "override_credit": None,
            "decision_rationale": "Stuck",
            "decision": "llm_stuck",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["decision"] == "STUCK"
        # None is falsy, so stuck_reason should NOT be set
        assert "stuck_reason" not in result

    def test_skip_when_complete(self):
        """Copies previous output when status is COMPLETE."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state(iteration=1)
        state["status_decision_maker"] = COMPLETE
        prev = {"decision": "proceed", "ambiguity_assessment": "ok",
                "missing_info_decision": False, "clarification_questions": [],
                "complexity_assessment": "ok", "llm_stuck": False, "stuck_reason": None,
                "classification_assessment": "ok", "debit_approved": True,
                "override_debit": None, "credit_approved": True, "override_credit": None,
                "decision_rationale": "ok"}
        state["output_decision_maker"] = [prev]

        result = decision_maker_node(state, {})

        assert result["status_decision_maker"] == COMPLETE
        assert len(result["output_decision_maker"]) == 2
        assert result["output_decision_maker"][1] == prev

    def test_override_classifications(self):
        """Decision maker can override debit/credit classifications."""
        from services.agent.nodes.decision_maker import decision_maker_node

        state = _make_state()
        output = {
            "ambiguity_assessment": "N/A",
            "missing_info_decision": False,
            "clarification_questions": [],
            "complexity_assessment": "N/A",
            "llm_stuck": False,
            "stuck_reason": None,
            "classification_assessment": "Debit should be asset, not expense",
            "debit_approved": False,
            "override_debit": [1, 0, 0, 0, 0, 0],
            "credit_approved": False,
            "override_credit": [0, 0, 0, 1, 0, 0],
            "decision_rationale": "Corrected classification",
            "decision": "proceed",
        }
        with patch("services.agent.nodes.decision_maker.invoke_structured", return_value=output), \
             patch("services.agent.nodes.decision_maker.get_llm", return_value=MagicMock()):
            result = decision_maker_node(state, {})

        assert result["output_decision_maker"][0]["debit_approved"] is False
        assert result["output_decision_maker"][0]["override_debit"] == [1, 0, 0, 0, 0, 0]


# ── Entry Drafter ────────────────────────────────────────────────────────

class TestEntryDrafterNode:
    """Tests for entry_drafter_node."""

    def test_basic_entry(self):
        """Normal entry with reason and lines."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state()
        output = {
            "reason": "Rent expense paid from cash",
            "lines": [
                {"type": "debit", "account_name": "Occupancy expense", "amount": 2000.0},
                {"type": "credit", "account_name": "Cash and cash equivalents", "amount": 2000.0},
            ],
        }
        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=[]):
            result = entry_drafter_node(state, {})

        assert result["status_entry_drafter"] == COMPLETE
        assert len(result["output_entry_drafter"]) == 1
        assert result["output_entry_drafter"][0]["reason"] == "Rent expense paid from cash"
        assert len(result["output_entry_drafter"][0]["lines"]) == 2

    def test_sets_approved_when_no_decision_maker(self):
        """Sets decision to APPROVED when no decision_maker ran (confident mode)."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state()
        state["decision"] = None  # no decision_maker ran
        output = {
            "reason": "Rent expense",
            "lines": [
                {"type": "debit", "account_name": "Occupancy expense", "amount": 2000.0},
                {"type": "credit", "account_name": "Cash", "amount": 2000.0},
            ],
        }
        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=[]):
            result = entry_drafter_node(state, {})

        assert result["decision"] == "APPROVED"

    def test_does_not_override_existing_decision(self):
        """Does not set decision if decision_maker already set one."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state()
        state["decision"] = "INCOMPLETE_INFORMATION"
        output = {
            "reason": "Attempted entry",
            "lines": [
                {"type": "debit", "account_name": "Occupancy expense", "amount": 2000.0},
                {"type": "credit", "account_name": "Cash", "amount": 2000.0},
            ],
        }
        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=[]):
            result = entry_drafter_node(state, {})

        assert "decision" not in result

    def test_skip_when_complete(self):
        """Copies previous output when status is COMPLETE."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state(iteration=1)
        state["status_entry_drafter"] = COMPLETE
        prev = {"reason": "prev", "lines": [
            {"type": "debit", "account_name": "A", "amount": 100.0},
            {"type": "credit", "account_name": "B", "amount": 100.0},
        ]}
        state["output_entry_drafter"] = [prev]

        result = entry_drafter_node(state, {})

        assert result["status_entry_drafter"] == COMPLETE
        assert len(result["output_entry_drafter"]) == 2
        assert result["output_entry_drafter"][1] == prev

    def test_needs_calculation_triggers_calc_step(self):
        """Transactions with calc keywords trigger _run_calculator_step."""
        from services.agent.nodes.entry_drafter import entry_drafter_node, _needs_calculation

        # Verify keyword detection
        state_interest = _make_state(transaction_text="Loan interest at 5% rate")
        assert _needs_calculation(state_interest) is True

        state_simple = _make_state(transaction_text="Pay rent $2000")
        assert _needs_calculation(state_simple) is False

    def test_calculator_step_with_tool_calls(self):
        """Calculator step executes tool calls and injects computed values."""
        from services.agent.nodes.entry_drafter import _run_calculator_step

        mock_response = MagicMock()
        mock_response.tool_calls = [
            {"args": {"expression": "1000 * 0.05"}}
        ]
        mock_calc_llm = MagicMock()
        mock_calc_llm.invoke.return_value = mock_response
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_calc_llm

        result = _run_calculator_step(mock_llm, [])

        assert result == "1000 * 0.05 = 50.0"

    def test_calculator_step_no_tool_calls(self):
        """Calculator step returns None when LLM does not request tools."""
        from services.agent.nodes.entry_drafter import _run_calculator_step

        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_calc_llm = MagicMock()
        mock_calc_llm.invoke.return_value = mock_response
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_calc_llm

        result = _run_calculator_step(mock_llm, [])

        assert result is None

    def test_calculator_step_error_returns_none(self):
        """Calculator step returns None on exception."""
        from services.agent.nodes.entry_drafter import _run_calculator_step

        mock_llm = MagicMock()
        mock_llm.bind_tools.side_effect = Exception("API error")

        result = _run_calculator_step(mock_llm, [])

        assert result is None

    def test_calculator_injects_computed_values(self):
        """Full node test: calc keywords trigger calculator, computed values injected."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state(transaction_text="Loan interest at 5% rate on $10000")
        output = {
            "reason": "Interest expense on loan",
            "lines": [
                {"type": "debit", "account_name": "Interest expense", "amount": 500.0},
                {"type": "credit", "account_name": "Cash", "amount": 500.0},
            ],
        }
        prompt_messages = []

        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=prompt_messages), \
             patch("services.agent.nodes.entry_drafter._run_calculator_step", return_value="10000 * 0.05 = 500.0"):
            result = entry_drafter_node(state, {})

        assert result["status_entry_drafter"] == COMPLETE
        # Verify a HumanMessage was appended with computed values
        assert len(prompt_messages) == 1
        assert "500.0" in str(prompt_messages[0].content)

    def test_calculator_none_does_not_inject(self):
        """When calculator returns None, no extra message is appended."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state(transaction_text="Loan interest at 5% rate")
        output = {
            "reason": "Interest expense",
            "lines": [
                {"type": "debit", "account_name": "Interest expense", "amount": 50.0},
                {"type": "credit", "account_name": "Cash", "amount": 50.0},
            ],
        }
        prompt_messages = []

        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=prompt_messages), \
             patch("services.agent.nodes.entry_drafter._run_calculator_step", return_value=None):
            result = entry_drafter_node(state, {})

        assert result["status_entry_drafter"] == COMPLETE
        assert len(prompt_messages) == 0  # no message injected

    def test_multi_line_entry(self):
        """Entry with more than 2 lines (e.g. tax)."""
        from services.agent.nodes.entry_drafter import entry_drafter_node

        state = _make_state(transaction_text="Buy supplies $100 + HST $13")
        output = {
            "reason": "Office supplies with HST",
            "lines": [
                {"type": "debit", "account_name": "Office supplies", "amount": 100.0},
                {"type": "debit", "account_name": "HST receivable", "amount": 13.0},
                {"type": "credit", "account_name": "Cash", "amount": 113.0},
            ],
        }
        with patch("services.agent.nodes.entry_drafter.invoke_structured", return_value=output), \
             patch("services.agent.nodes.entry_drafter.get_llm", return_value=MagicMock()), \
             patch("services.agent.nodes.entry_drafter.build_prompt", return_value=[]):
            result = entry_drafter_node(state, {})

        assert len(result["output_entry_drafter"][0]["lines"]) == 3


# ── Merge Lines (non-LLM) ───────────────────────────────────────────────

class TestMergeLinesNode:
    """Tests for merge_lines_node — pure Python, no LLM mocking needed."""

    def test_no_merge_needed(self):
        """Returns empty dict when all lines are already unique."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Rent",
            "lines": [
                {"type": "debit", "account_name": "Occupancy expense", "amount": 2000.0},
                {"type": "credit", "account_name": "Cash", "amount": 2000.0},
            ],
        }]

        result = merge_lines_node(state)

        assert result == {}  # nothing to merge

    def test_merge_duplicate_debits(self):
        """Merges two debit lines with the same account."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Split purchase",
            "lines": [
                {"type": "debit", "account_name": "Office supplies", "amount": 100.0},
                {"type": "debit", "account_name": "Office supplies", "amount": 50.0},
                {"type": "credit", "account_name": "Cash", "amount": 150.0},
            ],
        }]

        result = merge_lines_node(state)

        assert "output_entry_drafter" in result
        lines = result["output_entry_drafter"][-1]["lines"]
        assert len(lines) == 2
        debit_line = [l for l in lines if l["type"] == "debit"][0]
        assert debit_line["amount"] == 150.0
        assert debit_line["account_name"] == "Office supplies"

    def test_merge_duplicate_credits(self):
        """Merges two credit lines with the same account."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Multiple payments",
            "lines": [
                {"type": "debit", "account_name": "Expense", "amount": 300.0},
                {"type": "credit", "account_name": "Cash", "amount": 200.0},
                {"type": "credit", "account_name": "Cash", "amount": 100.0},
            ],
        }]

        result = merge_lines_node(state)

        lines = result["output_entry_drafter"][-1]["lines"]
        assert len(lines) == 2
        credit_line = [l for l in lines if l["type"] == "credit"][0]
        assert credit_line["amount"] == 300.0

    def test_same_account_different_type_not_merged(self):
        """Lines with same account but different type (debit vs credit) are not merged."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Contra entry",
            "lines": [
                {"type": "debit", "account_name": "Cash", "amount": 500.0},
                {"type": "credit", "account_name": "Cash", "amount": 500.0},
            ],
        }]

        result = merge_lines_node(state)

        assert result == {}  # 2 unique keys, no merge

    def test_empty_output_entry_drafter(self):
        """Returns empty dict when output_entry_drafter is empty."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = []

        result = merge_lines_node(state)

        assert result == {}

    def test_none_entry(self):
        """Returns empty dict when the latest entry is None."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [None]

        result = merge_lines_node(state)

        assert result == {}

    def test_empty_lines(self):
        """Returns empty dict when lines list is empty."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{"reason": "test", "lines": []}]

        result = merge_lines_node(state)

        assert result == {}

    def test_preserves_reason(self):
        """Merged output preserves the original reason field."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Important reasoning text",
            "lines": [
                {"type": "debit", "account_name": "A", "amount": 10.0},
                {"type": "debit", "account_name": "A", "amount": 20.0},
                {"type": "credit", "account_name": "B", "amount": 30.0},
            ],
        }]

        result = merge_lines_node(state)

        assert result["output_entry_drafter"][-1]["reason"] == "Important reasoning text"

    def test_preserves_order(self):
        """Merged lines maintain the order of first appearance."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Order test",
            "lines": [
                {"type": "debit", "account_name": "Expense A", "amount": 100.0},
                {"type": "credit", "account_name": "Cash", "amount": 50.0},
                {"type": "debit", "account_name": "Expense A", "amount": 50.0},
                {"type": "credit", "account_name": "Cash", "amount": 100.0},
            ],
        }]

        result = merge_lines_node(state)

        lines = result["output_entry_drafter"][-1]["lines"]
        assert len(lines) == 2
        assert lines[0]["type"] == "debit"
        assert lines[0]["account_name"] == "Expense A"
        assert lines[0]["amount"] == 150.0
        assert lines[1]["type"] == "credit"
        assert lines[1]["account_name"] == "Cash"
        assert lines[1]["amount"] == 150.0

    def test_rounding(self):
        """Merged amounts are rounded to 2 decimal places."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Rounding test",
            "lines": [
                {"type": "debit", "account_name": "A", "amount": 10.333},
                {"type": "debit", "account_name": "A", "amount": 10.333},
                {"type": "credit", "account_name": "B", "amount": 20.666},
            ],
        }]

        result = merge_lines_node(state)

        lines = result["output_entry_drafter"][-1]["lines"]
        assert lines[0]["amount"] == 20.67  # round(20.666, 2)

    def test_mutates_last_entry_in_history(self):
        """Merge replaces the last entry in history, preserving earlier entries."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        entry_0 = {"reason": "v0", "lines": [
            {"type": "debit", "account_name": "X", "amount": 10.0},
            {"type": "credit", "account_name": "Y", "amount": 10.0},
        ]}
        entry_1 = {"reason": "v1", "lines": [
            {"type": "debit", "account_name": "A", "amount": 50.0},
            {"type": "debit", "account_name": "A", "amount": 50.0},
            {"type": "credit", "account_name": "B", "amount": 100.0},
        ]}
        state["output_entry_drafter"] = [entry_0, entry_1]

        result = merge_lines_node(state)

        history = result["output_entry_drafter"]
        assert len(history) == 2
        # First entry is preserved
        assert history[0] == entry_0
        # Second entry is merged
        assert len(history[1]["lines"]) == 2
        assert history[1]["lines"][0]["amount"] == 100.0

    def test_three_duplicates_summed(self):
        """Three lines with the same key are summed into one."""
        from services.agent.nodes.non_llm.merge_lines import merge_lines_node

        state = _make_state()
        state["output_entry_drafter"] = [{
            "reason": "Triple",
            "lines": [
                {"type": "debit", "account_name": "A", "amount": 10.0},
                {"type": "debit", "account_name": "A", "amount": 20.0},
                {"type": "debit", "account_name": "A", "amount": 30.0},
                {"type": "credit", "account_name": "B", "amount": 60.0},
            ],
        }]

        result = merge_lines_node(state)

        lines = result["output_entry_drafter"][-1]["lines"]
        assert len(lines) == 2
        assert lines[0]["amount"] == 60.0
