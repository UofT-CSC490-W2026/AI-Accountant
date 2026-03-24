"""Router functions for conditional edges in the pipeline graph.

Each function reads state, returns a node name string.
No state mutation, no LLM calls — pure routing decisions.
"""
from langgraph.graph import END

from services.agent.graph.state import PipelineState


def route_after_start(state: PipelineState, config=None) -> str:
    """Skip disambiguator if inactive."""
    configurable = (config or {}).get("configurable", {})
    if configurable.get("disambiguator_active", True):
        return "disambiguator"
    return "classifiers"


def route_before_correctors(state: PipelineState, config=None) -> str:
    """Skip correctors if correction_pass is disabled."""
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("correction_pass", True):
        return "corrector_passthrough"
    return "correctors"


def route_before_approver(state: PipelineState, config=None) -> str:
    """Skip evaluator if evaluation_active is disabled."""
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("evaluation_active", True):
        return "confidence_gate"
    return "approver"


def route_after_approver(state: PipelineState) -> str:
    """Approved → confidence gate. Rejected → diagnostician."""
    i = state["iteration"]
    approval = state["output_approver"][i]
    if approval["approved"]:
        return "confidence_gate"
    return "diagnostician"


def route_after_diagnostician(state: PipelineState) -> str:
    """FIX → fix scheduler. STUCK or max iterations → END."""
    i = state["iteration"]
    diagnosis = state["output_diagnostician"][i]
    if diagnosis["decision"] == "STUCK" or i >= 1:  # max 2 iterations (0 and 1)
        return END
    return "fix_scheduler"


def route_after_confidence_gate(state: PipelineState) -> str:
    """Route based on confidence gate result."""
    return state.get("route", "clarify")
