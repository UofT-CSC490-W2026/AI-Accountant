from __future__ import annotations

from services.agent.graph.state import RERUN
from services.agent.nodes.non_llm.fix_scheduler import fix_scheduler_node


def _make_state(
    iteration: int = 0,
    fix_plans: list[dict] | None = None,
    **overrides,
) -> dict:
    """Build a minimal state for fix_scheduler_node."""
    if fix_plans is None:
        fix_plans = [{"agent": 1, "fix_context": "Reclassify as expense"}]

    state = {
        "iteration": iteration,
        "output_diagnostician": [
            {"decision": "FIX", "fix_plans": fix_plans, "reasoning": "test"}
        ],
        # Fix context histories (initially empty)
        "fix_context_disambiguator": [],
        "fix_context_debit_classifier": [],
        "fix_context_credit_classifier": [],
        "fix_context_debit_corrector": [],
        "fix_context_credit_corrector": [],
        "fix_context_entry_builder": [],
        "fix_context_approver": [],
        "fix_context_diagnostician": [],
    }
    state.update(overrides)
    return state


class TestFixSchedulerNode:
    def test_increments_iteration(self):
        state = _make_state(iteration=0)
        result = fix_scheduler_node(state)
        assert result["iteration"] == 1

    def test_sets_rerun_for_dirty_agents(self):
        """Agent 1 dirty => agents 1, 3, 4, 5 get RERUN status."""
        state = _make_state(
            fix_plans=[{"agent": 1, "fix_context": "fix debit"}],
        )
        result = fix_scheduler_node(state)
        assert result.get("status_debit_classifier") == RERUN
        assert result.get("status_debit_corrector") == RERUN
        assert result.get("status_credit_corrector") == RERUN
        assert result.get("status_entry_builder") == RERUN
        # Clean agents should NOT be in the update
        assert "status_disambiguator" not in result
        assert "status_credit_classifier" not in result

    def test_distributes_fix_context(self):
        """Fix context is appended to the target agent's history."""
        state = _make_state(
            fix_plans=[{"agent": 1, "fix_context": "Reclassify as expense"}],
        )
        result = fix_scheduler_node(state)
        assert result["fix_context_debit_classifier"] == ["Reclassify as expense"]

    def test_multiple_fix_plans(self):
        """Multiple fix plans distribute to multiple agents."""
        state = _make_state(
            fix_plans=[
                {"agent": 1, "fix_context": "Fix debit"},
                {"agent": 2, "fix_context": "Fix credit"},
            ],
        )
        result = fix_scheduler_node(state)
        assert result["fix_context_debit_classifier"] == ["Fix debit"]
        assert result["fix_context_credit_classifier"] == ["Fix credit"]

    def test_clears_stale_embeddings(self):
        result = fix_scheduler_node(_make_state())
        assert result["embedding_error"] is None
        assert result["embedding_rejection"] is None

    def test_appends_to_existing_fix_context(self):
        """On second fix iteration, appends rather than overwrites."""
        state = _make_state(
            iteration=0,
            fix_plans=[{"agent": 1, "fix_context": "Second fix"}],
            fix_context_debit_classifier=["First fix"],
        )
        result = fix_scheduler_node(state)
        assert result["fix_context_debit_classifier"] == ["First fix", "Second fix"]

    def test_agent_0_dirties_all(self):
        """Fixing disambiguator (agent 0) reruns all 6 agents."""
        state = _make_state(
            fix_plans=[{"agent": 0, "fix_context": "Redo disambiguation"}],
        )
        result = fix_scheduler_node(state)
        assert result.get("status_disambiguator") == RERUN
        assert result.get("status_debit_classifier") == RERUN
        assert result.get("status_credit_classifier") == RERUN
        assert result.get("status_debit_corrector") == RERUN
        assert result.get("status_credit_corrector") == RERUN
        assert result.get("status_entry_builder") == RERUN
