from __future__ import annotations

import sys
from types import ModuleType

# ── Mock langgraph before importing the module under test ─────────────────
# END in langgraph equals the string "__end__"

_mock_langgraph_graph = ModuleType("langgraph.graph")
_mock_langgraph_graph.END = "__end__"

_mock_langgraph = ModuleType("langgraph")
_mock_langgraph.graph = _mock_langgraph_graph

sys.modules.setdefault("langgraph", _mock_langgraph)
sys.modules.setdefault("langgraph.graph", _mock_langgraph_graph)

from services.agent.graph.routers.routing import (
    route_after_start,
    route_after_disambiguator,
    route_before_correctors,
    route_after_validation,
    route_after_approver,
    route_after_diagnostician,
)

END = "__end__"


# ── route_after_start ─────────────────────────────────────────────────────

class TestRouteAfterStart:
    def test_disambiguator_active_returns_disambiguator(self):
        config = {"configurable": {"disambiguator_active": True}}
        result = route_after_start({}, config)
        assert result == "disambiguator"

    def test_disambiguator_inactive_returns_classifiers(self):
        config = {"configurable": {"disambiguator_active": False}}
        result = route_after_start({}, config)
        assert result == ["debit_classifier", "credit_classifier"]

    def test_default_config_returns_disambiguator(self):
        """No config => disambiguator_active defaults to True."""
        result = route_after_start({}, None)
        assert result == "disambiguator"

    def test_empty_config_returns_disambiguator(self):
        result = route_after_start({}, {})
        assert result == "disambiguator"


# ── route_after_disambiguator ─────────────────────────────────────────────

class TestRouteAfterDisambiguator:
    def test_always_returns_classifiers(self):
        result = route_after_disambiguator({})
        assert result == ["debit_classifier", "credit_classifier"]


# ── route_before_correctors ───────────────────────────────────────────────

class TestRouteBeforeCorrectors:
    def test_correction_active_returns_correctors(self):
        config = {"configurable": {"correction_active": True}}
        result = route_before_correctors({}, config)
        assert result == "correctors"

    def test_correction_inactive_returns_passthrough(self):
        config = {"configurable": {"correction_active": False}}
        result = route_before_correctors({}, config)
        assert result == "corrector_passthrough"

    def test_default_returns_correctors(self):
        result = route_before_correctors({}, None)
        assert result == "correctors"


# ── route_after_validation ────────────────────────────────────────────────

class TestRouteAfterValidation:
    def test_validation_error_returns_end(self):
        state = {"validation_error": ["Debits != Credits"]}
        result = route_after_validation(state)
        assert result == "end"

    def test_incomplete_information_returns_end(self):
        state = {"decision": "INCOMPLETE_INFORMATION", "validation_error": None}
        result = route_after_validation(state)
        assert result == "end"

    def test_evaluation_inactive_returns_end(self):
        state = {"validation_error": None, "decision": None}
        config = {"configurable": {"evaluation_active": False}}
        result = route_after_validation(state, config)
        assert result == "end"

    def test_all_good_returns_approver(self):
        state = {"validation_error": None, "decision": None}
        config = {"configurable": {"evaluation_active": True}}
        result = route_after_validation(state, config)
        assert result == "approver"

    def test_default_config_returns_approver(self):
        state = {"validation_error": None, "decision": None}
        result = route_after_validation(state, None)
        assert result == "approver"


# ── route_after_approver ──────────────────────────────────────────────────

class TestRouteAfterApprover:
    def test_approved_returns_end(self):
        state = {
            "iteration": 0,
            "output_approver": [{"decision": "APPROVED", "confidence": "VERY_CONFIDENT", "reason": "ok"}],
        }
        result = route_after_approver(state)
        assert result == END

    def test_stuck_returns_end(self):
        state = {
            "iteration": 0,
            "output_approver": [{"decision": "STUCK", "confidence": "VERY_UNCERTAIN", "reason": "can't"}],
        }
        result = route_after_approver(state)
        assert result == END

    def test_rejected_returns_diagnostician(self):
        state = {
            "iteration": 0,
            "output_approver": [{"decision": "REJECTED", "confidence": "SOMEWHAT_CONFIDENT", "reason": "wrong"}],
        }
        result = route_after_approver(state)
        assert result == "diagnostician"

    def test_reads_correct_iteration(self):
        state = {
            "iteration": 1,
            "output_approver": [
                {"decision": "REJECTED", "confidence": "x", "reason": "y"},
                {"decision": "APPROVED", "confidence": "x", "reason": "y"},
            ],
        }
        result = route_after_approver(state)
        assert result == END


# ── route_after_diagnostician ─────────────────────────────────────────────

class TestRouteAfterDiagnostician:
    def test_fix_returns_fix_scheduler(self):
        state = {
            "iteration": 0,
            "output_diagnostician": [{"decision": "FIX", "fix_plans": [{"agent": 1, "fix_context": "x"}]}],
        }
        result = route_after_diagnostician(state)
        assert result == "fix_scheduler"

    def test_stuck_returns_end(self):
        state = {
            "iteration": 0,
            "output_diagnostician": [{"decision": "STUCK", "fix_plans": [], "stuck_reason": "can't"}],
        }
        result = route_after_diagnostician(state)
        assert result == END

    def test_max_iterations_returns_end(self):
        """At iteration >= 1, always END regardless of decision."""
        state = {
            "iteration": 1,
            "output_diagnostician": [
                {"decision": "FIX", "fix_plans": [{"agent": 1, "fix_context": "x"}]},
                {"decision": "FIX", "fix_plans": [{"agent": 1, "fix_context": "y"}]},
            ],
        }
        result = route_after_diagnostician(state)
        assert result == END

    def test_iteration_0_fix_allowed(self):
        """At iteration 0, FIX proceeds to fix_scheduler."""
        state = {
            "iteration": 0,
            "output_diagnostician": [{"decision": "FIX", "fix_plans": [{"agent": 0, "fix_context": "z"}]}],
        }
        result = route_after_diagnostician(state)
        assert result == "fix_scheduler"
