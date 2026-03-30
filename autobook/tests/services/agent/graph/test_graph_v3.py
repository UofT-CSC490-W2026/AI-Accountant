"""Tests for V3 agent pipeline graph routing functions.

Tests the pure-Python routing logic without importing the full graph
(which requires langgraph). The routing functions are extracted and tested
directly.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ── Stub external deps needed by transitive imports ───────────────────────

_lc_core = sys.modules.setdefault("langchain_core", ModuleType("langchain_core"))
_lc_msgs = sys.modules.setdefault("langchain_core.messages", ModuleType("langchain_core.messages"))
def _msg_init(self, content, **kwargs):
    self.content = content
    for k, v in kwargs.items():
        setattr(self, k, v)

_lc_msgs.SystemMessage = type("SystemMessage", (), {"__init__": _msg_init, "type": "system"})
_lc_msgs.HumanMessage = type("HumanMessage", (), {"__init__": _msg_init, "type": "human"})
_lc_msgs.AIMessage = type("AIMessage", (), {"__init__": _msg_init, "type": "ai"})
_lc_msgs.ToolMessage = type("ToolMessage", (), {"__init__": _msg_init, "type": "tool"})
_lc_core.messages = _lc_msgs
_lc_runnables = sys.modules.setdefault("langchain_core.runnables", ModuleType("langchain_core.runnables"))
_lc_runnables.RunnableConfig = dict
_lc_callbacks = sys.modules.setdefault("langchain_core.callbacks", ModuleType("langchain_core.callbacks"))
_lc_callbacks.BaseCallbackHandler = type("BaseCallbackHandler", (), {})
_lc_tools = sys.modules.setdefault("langchain_core.tools", ModuleType("langchain_core.tools"))
_lc_tools.tool = lambda f: f
_lc_aws = sys.modules.setdefault("langchain_aws", ModuleType("langchain_aws"))
_lc_aws.ChatBedrockConverse = MagicMock()

# Stub langgraph — graph_v3 uses StateGraph at module level
_lg = sys.modules.setdefault("langgraph", ModuleType("langgraph"))
_lg_graph = sys.modules.setdefault("langgraph.graph", ModuleType("langgraph.graph"))
_mock_builder = MagicMock()
_mock_builder.compile.return_value = MagicMock(name="compiled_app")
_lg_graph.StateGraph = MagicMock(return_value=_mock_builder)
_lg_graph.END = "__end__"
_lg_types = sys.modules.setdefault("langgraph.types", ModuleType("langgraph.types"))
_lg_types.RetryPolicy = MagicMock()

from services.agent.graph.state import AGENT_NAMES, NOT_RUN  # noqa: E402

# Import graph_v3 routing functions — these are pure Python
from services.agent.graph.graph_v3 import (  # noqa: E402
    route_layer1_start,
    route_after_layer1,
    route_after_decision,
    layer1_join_node,
    app,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_state(**overrides):
    state = {
        "transaction_text": "Pay rent $2000",
        "user_context": {"province": "ON", "entity_type": "corporation"},
        "ml_enrichment": None,
        "iteration": 0,
        "decision": None,
        "validation_error": None,
        "clarification_questions": None,
        "stuck_reason": None,
        "embedding_transaction": None,
        "embedding_error": None,
        "embedding_rejection": None,
    }
    for name in AGENT_NAMES:
        state[f"output_{name}"] = []
        state[f"status_{name}"] = NOT_RUN
        state.setdefault(f"fix_context_{name}", [])
        state.setdefault(f"rag_cache_{name}", [])
    state.update(overrides)
    return state


# ── Tests: module-level compilation ─────────────────────────────────────

class TestGraphCompilation:
    def test_app_exists(self):
        assert app is not None

    def test_builder_compiled(self):
        _mock_builder.compile.assert_called()

    def test_layer1_nodes_registered(self):
        node_names = [c.args[0] for c in _mock_builder.add_node.call_args_list]
        for name in ["ambiguity_detector", "complexity_detector",
                      "debit_classifier", "credit_classifier", "tax_specialist"]:
            assert name in node_names

    def test_layer2_nodes_registered(self):
        node_names = [c.args[0] for c in _mock_builder.add_node.call_args_list]
        assert "decision_maker" in node_names
        assert "entry_drafter" in node_names

    def test_merge_lines_node_registered(self):
        node_names = [c.args[0] for c in _mock_builder.add_node.call_args_list]
        assert "merge_lines" in node_names

    def test_layer1_join_registered(self):
        node_names = [c.args[0] for c in _mock_builder.add_node.call_args_list]
        assert "layer1_join" in node_names


# ── Tests: route_layer1_start ───────────────────────────────────────────

class TestRouteLayer1Start:
    def test_returns_all_five(self):
        state = _make_state()
        result = route_layer1_start(state)
        assert set(result) == {
            "ambiguity_detector", "complexity_detector",
            "debit_classifier", "credit_classifier", "tax_specialist",
        }

    def test_returns_list(self):
        state = _make_state()
        assert isinstance(route_layer1_start(state), list)
        assert len(route_layer1_start(state)) == 5


# ── Tests: route_after_layer1 ──────────────────────────────────────────

class TestRouteAfterLayer1:
    def test_all_clear_routes_to_entry_drafter(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": []}],
            output_complexity_detector=[{"flags": []}],
        )
        assert route_after_layer1(state) == "entry_drafter"

    def test_unresolved_ambiguity_routes_to_decision_maker(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": [{"aspect": "purpose", "resolved": False}]}],
            output_complexity_detector=[{"flags": []}],
        )
        assert route_after_layer1(state) == "decision_maker"

    def test_resolved_ambiguity_routes_to_entry_drafter(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": [{"aspect": "purpose", "resolved": True}]}],
            output_complexity_detector=[{"flags": []}],
        )
        assert route_after_layer1(state) == "entry_drafter"

    def test_skeptical_complexity_routes_to_decision_maker(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": []}],
            output_complexity_detector=[{"flags": [{"category": "multi-step", "skeptical": True}]}],
        )
        assert route_after_layer1(state) == "decision_maker"

    def test_non_skeptical_routes_to_entry_drafter(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": []}],
            output_complexity_detector=[{"flags": [{"category": "multi-step", "skeptical": False}]}],
        )
        assert route_after_layer1(state) == "entry_drafter"

    def test_both_flagged_routes_to_decision_maker(self):
        state = _make_state(
            output_ambiguity_detector=[{"ambiguities": [{"aspect": "type", "resolved": False}]}],
            output_complexity_detector=[{"flags": [{"category": "tax", "skeptical": True}]}],
        )
        assert route_after_layer1(state) == "decision_maker"

    def test_empty_outputs_routes_to_entry_drafter(self):
        state = _make_state(output_ambiguity_detector=[], output_complexity_detector=[])
        assert route_after_layer1(state) == "entry_drafter"

    def test_uses_last_output(self):
        state = _make_state(
            output_ambiguity_detector=[
                {"ambiguities": [{"aspect": "x", "resolved": False}]},
                {"ambiguities": []},
            ],
            output_complexity_detector=[{"flags": []}],
        )
        assert route_after_layer1(state) == "entry_drafter"


# ── Tests: route_after_decision ─────────────────────────────────────────

class TestRouteAfterDecision:
    def test_proceed_routes_to_entry_drafter(self):
        state = _make_state(output_decision_maker=[{"decision": "proceed"}])
        assert route_after_decision(state) == "entry_drafter"

    def test_non_proceed_routes_to_end(self):
        state = _make_state(output_decision_maker=[{"decision": "reject"}])
        assert route_after_decision(state) == "end"

    def test_no_output_routes_to_end(self):
        state = _make_state(output_decision_maker=[])
        assert route_after_decision(state) == "end"

    def test_missing_decision_key_routes_to_end(self):
        state = _make_state(output_decision_maker=[{"some_other_key": "value"}])
        assert route_after_decision(state) == "end"


# ── Tests: layer1_join_node ─────────────────────────────────────────────

class TestLayer1JoinNode:
    def test_returns_empty_dict(self):
        state = _make_state()
        assert layer1_join_node(state) == {}

    def test_does_not_modify_state(self):
        state = _make_state()
        original_keys = set(state.keys())
        layer1_join_node(state)
        assert set(state.keys()) == original_keys
