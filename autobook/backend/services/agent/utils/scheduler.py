"""Dependency table and dirty set computation for the fix loop.

Pure data utility — returns agent indices only. The graph node
(fix_scheduler_node in graph.py) handles state updates, iteration
increment, and fix_context distribution.
"""

# Dependency table from agent-pipeline.md — drives dirty propagation.
# When an agent is root cause, all downstream agents must rerun.
DEPENDENCY_TABLE: dict[int, dict] = {
    0: {"downstream": [0, 1, 2, 3, 4, 5], "parallel_with": []},
    1: {"downstream": [1, 3, 4, 5],        "parallel_with": [2]},
    2: {"downstream": [2, 3, 4, 5],        "parallel_with": [1]},
    3: {"downstream": [3, 5],              "parallel_with": [4]},
    4: {"downstream": [4, 5],              "parallel_with": [3]},
    5: {"downstream": [5],                 "parallel_with": []},
}

# Agent index → agent name mapping (generator agents only, 0-5)
AGENT_INDEX_TO_NAME: dict[int, str] = {
    0: "disambiguator",
    1: "debit_classifier",
    2: "credit_classifier",
    3: "debit_corrector",
    4: "credit_corrector",
    5: "entry_builder",
}


def compute_dirty_set(fix_plans: list[dict]) -> set[int]:
    """Compute which agent indices need rerunning.

    Pure function: fix_plans → set of dirty agent indices.
    Does not touch state — the graph node handles that.

    Args:
        fix_plans: Diagnostician output, e.g.
            [{"agent": 1, "error": "...", "fix_context": "..."}]

    Returns:
        Set of agent indices that need rerunning, e.g. {1, 3, 4, 5}
    """
    dirty: set[int] = set()
    for plan in fix_plans:
        agent_idx = plan["agent"]
        if agent_idx in DEPENDENCY_TABLE:
            dirty.update(DEPENDENCY_TABLE[agent_idx]["downstream"])
    return dirty
