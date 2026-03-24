from services.agent.graph.state import (
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    RERUN,
)

# Agent index → agent name mapping (generator agents only, 0-5)
_AGENT_INDEX_TO_NAME: dict[int, str] = {
    0: DISAMBIGUATOR,
    1: DEBIT_CLASSIFIER,
    2: CREDIT_CLASSIFIER,
    3: DEBIT_CORRECTOR,
    4: CREDIT_CORRECTOR,
    5: ENTRY_BUILDER,
}

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


def compute_rerun_statuses(fix_plans: list[dict]) -> dict[str, int]:
    """Compute which agents need rerunning based on diagnostician output.

    Uses dirty propagation: root cause agent + all downstream agents
    get status RERUN. LangGraph's graph topology handles execution
    ordering and parallelism — this function only computes the dirty set.

    Args:
        fix_plans: Diagnostician output, e.g.
            [{"agent": 1, "error": "...", "fix_context": "..."}]

    Returns:
        State update dict, e.g.
            {"status_debit_classifier": 2, "status_debit_corrector": 2,
             "status_entry_builder": 2}
    """
    dirty_indices: set[int] = set()
    for plan in fix_plans:
        agent_idx = plan["agent"]
        if agent_idx in DEPENDENCY_TABLE:
            dirty_indices.update(DEPENDENCY_TABLE[agent_idx]["downstream"])

    return {
        f"status_{_AGENT_INDEX_TO_NAME[idx]}": RERUN
        for idx in dirty_indices
        if idx in _AGENT_INDEX_TO_NAME
    }
