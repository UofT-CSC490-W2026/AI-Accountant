from __future__ import annotations

from services.agent.utils.prompt.reasoning import compile_reasoning_trace


def _make_state(**overrides) -> dict:
    """Build a minimal state dict with output_* fields for testing."""
    state = {
        "output_disambiguator": [],
        "output_debit_classifier": [],
        "output_credit_classifier": [],
        "output_debit_corrector": [],
        "output_credit_corrector": [],
        "output_entry_builder": [],
    }
    state.update(overrides)
    return state


class TestCompileReasoningTrace:
    def test_single_iteration_all_agents(self):
        state = _make_state(
            output_disambiguator=[{"ambiguities": []}],
            output_debit_classifier=[{"reason": "expense", "tuple": (0, 0, 1, 0, 0, 0)}],
            output_credit_classifier=[{"reason": "asset decrease", "tuple": (0, 0, 0, 1, 0, 0)}],
            output_debit_corrector=[{"reason": "ok", "tuple": (0, 0, 1, 0, 0, 0)}],
            output_credit_corrector=[{"reason": "ok", "tuple": (0, 0, 0, 1, 0, 0)}],
            output_entry_builder=[{"date": "2026-01-01", "lines": []}],
        )
        result = compile_reasoning_trace(state, iteration=0)
        assert "--- Iteration 0 ---" in result
        assert "Agent 0 (Disambiguator)" in result
        assert "Agent 1 (Debit Classifier)" in result
        assert "Agent 5 (Entry Builder)" in result

    def test_two_iterations(self):
        state = _make_state(
            output_disambiguator=["text_v0", "text_v1"],
            output_debit_classifier=[{"r": "a"}, {"r": "b"}],
            output_credit_classifier=[{"r": "a"}, {"r": "b"}],
            output_debit_corrector=[{"r": "a"}, {"r": "b"}],
            output_credit_corrector=[{"r": "a"}, {"r": "b"}],
            output_entry_builder=[{"date": "d0"}, {"date": "d1"}],
        )
        result = compile_reasoning_trace(state, iteration=1)
        assert "--- Iteration 0 ---" in result
        assert "--- Iteration 1 ---" in result

    def test_none_outputs_skipped(self):
        state = _make_state(
            output_disambiguator=[None],
            output_debit_classifier=[{"reason": "test", "tuple": (1, 0, 0, 0, 0, 0)}],
        )
        result = compile_reasoning_trace(state, iteration=0)
        assert "Agent 0 (Disambiguator)" not in result
        assert "Agent 1 (Debit Classifier)" in result

    def test_empty_state_produces_iteration_header_only(self):
        state = _make_state()
        result = compile_reasoning_trace(state, iteration=0)
        assert "--- Iteration 0 ---" in result
        # No agent output lines
        lines = [l for l in result.strip().split("\n") if l.startswith("Agent")]
        assert lines == []

    def test_partial_outputs(self):
        """Only some agents ran (e.g., iteration 1 where agent 0 was skipped)."""
        state = _make_state(
            output_disambiguator=[],  # not run in iteration 0
            output_debit_classifier=[{"r": "test"}],
        )
        result = compile_reasoning_trace(state, iteration=0)
        assert "Agent 0 (Disambiguator)" not in result
        assert "Agent 1 (Debit Classifier)" in result
