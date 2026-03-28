"""Fix scheduler node — orchestrates the fix loop.

Pure Python logic, no LLM. Computes dirty set, increments iteration,
distributes fix_context to targeted agents, clears stale embeddings.
"""
from services.agent.graph.state import PipelineState, RERUN
from services.agent.utils.scheduler import compute_dirty_set, AGENT_INDEX_TO_NAME


def fix_scheduler_node(state: PipelineState) -> dict:
    """Compute rerun set and prepare state for fix loop iteration."""
    # ── Read diagnosis ────────────────────────────────────────────
    i = state["iteration"]
    diagnosis = state["output_diagnostician"][i]
    fix_plans = diagnosis["fix_plans"]

    # ── Compute dirty set (pure util) ─────────────────────────────
    dirty = compute_dirty_set(fix_plans)

    # ── Build state update ────────────────────────────────────────
    update: dict = {"iteration": i + 1}

    # Set RERUN for dirty agents, leave clean agents as COMPLETE
    for idx, name in AGENT_INDEX_TO_NAME.items():
        if idx in dirty:
            update[f"status_{name}"] = RERUN

    # Distribute fix_context to targeted agents
    for plan in fix_plans:
        idx = plan["agent"]
        name = AGENT_INDEX_TO_NAME.get(idx)
        if name:
            existing = list(state.get(f"fix_context_{name}", []))
            existing.append(plan.get("fix_context", ""))
            update[f"fix_context_{name}"] = existing

    # Clear stale embeddings (for multi-fix support)
    update["embedding_error"] = None
    update["embedding_rejection"] = None

    return update
