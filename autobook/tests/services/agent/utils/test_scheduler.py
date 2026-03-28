from __future__ import annotations

from services.agent.utils.scheduler import compute_dirty_set, DEPENDENCY_TABLE, AGENT_INDEX_TO_NAME


class TestComputeDirtySet:
    """Tests for compute_dirty_set(fix_plans) -> set[int]."""

    def test_single_root_cause_agent_1(self):
        """Agent 1 dirty => downstream {1, 3, 4, 5}."""
        fix_plans = [{"agent": 1, "error": "wrong", "fix_context": "fix it"}]
        result = compute_dirty_set(fix_plans)
        assert result == {1, 3, 4, 5}

    def test_single_root_cause_agent_0(self):
        """Agent 0 dirty => all agents {0, 1, 2, 3, 4, 5}."""
        fix_plans = [{"agent": 0, "error": "bad", "fix_context": "redo"}]
        result = compute_dirty_set(fix_plans)
        assert result == {0, 1, 2, 3, 4, 5}

    def test_single_root_cause_agent_5(self):
        """Agent 5 dirty => only itself {5}."""
        fix_plans = [{"agent": 5, "error": "bad entry", "fix_context": "fix"}]
        result = compute_dirty_set(fix_plans)
        assert result == {5}

    def test_multiple_root_causes(self):
        """Agents 1 and 2 dirty => union of their downstream sets."""
        fix_plans = [
            {"agent": 1, "error": "a", "fix_context": "x"},
            {"agent": 2, "error": "b", "fix_context": "y"},
        ]
        result = compute_dirty_set(fix_plans)
        # downstream(1) = {1,3,4,5}, downstream(2) = {2,3,4,5}
        assert result == {1, 2, 3, 4, 5}

    def test_multiple_root_causes_agent_3_and_4(self):
        """Agents 3 and 4 dirty => {3, 4, 5}."""
        fix_plans = [
            {"agent": 3, "error": "a", "fix_context": "x"},
            {"agent": 4, "error": "b", "fix_context": "y"},
        ]
        result = compute_dirty_set(fix_plans)
        assert result == {3, 4, 5}

    def test_empty_fix_plans(self):
        """No root causes => empty set."""
        result = compute_dirty_set([])
        assert result == set()

    def test_unknown_agent_index_ignored(self):
        """Agent index not in DEPENDENCY_TABLE (e.g. 99) is ignored."""
        fix_plans = [{"agent": 99, "error": "?", "fix_context": "?"}]
        result = compute_dirty_set(fix_plans)
        assert result == set()

    def test_duplicate_root_causes(self):
        """Same agent listed twice => same result as once (set union is idempotent)."""
        fix_plans = [
            {"agent": 1, "error": "a", "fix_context": "x"},
            {"agent": 1, "error": "b", "fix_context": "y"},
        ]
        result = compute_dirty_set(fix_plans)
        assert result == {1, 3, 4, 5}


class TestConstants:
    """Sanity checks for module-level constants."""

    def test_dependency_table_has_all_six_agents(self):
        assert set(DEPENDENCY_TABLE.keys()) == {0, 1, 2, 3, 4, 5}

    def test_agent_index_to_name_has_all_six(self):
        assert set(AGENT_INDEX_TO_NAME.keys()) == {0, 1, 2, 3, 4, 5}
        assert AGENT_INDEX_TO_NAME[0] == "disambiguator"
        assert AGENT_INDEX_TO_NAME[5] == "entry_builder"

    def test_every_agent_includes_self_in_downstream(self):
        for idx, info in DEPENDENCY_TABLE.items():
            assert idx in info["downstream"], f"Agent {idx} missing from own downstream"
