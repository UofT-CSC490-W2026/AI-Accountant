"""Router functions for conditional edges in the pipeline graph.

Each function reads state, returns a node name string.
No state mutation, no LLM calls — pure routing decisions.
"""
from langgraph.graph import END

from services.agent.graph.state import PipelineState


def route_after_start(state: PipelineState, config=None) -> str | list[str]:
    """Skip disambiguator if inactive. Returns list for parallel fan-out."""
    configurable = (config or {}).get("configurable", {})
    if configurable.get("disambiguator_active", True):
        return "disambiguator"
    return ["debit_classifier", "credit_classifier"]


def route_after_disambiguator(state: PipelineState) -> list[str]:
    """Always proceed to classifiers. Disambiguator is advisory, not a gate."""
    return ["debit_classifier", "credit_classifier"]


def route_before_correctors(state: PipelineState, config=None) -> str:
    """Skip correctors if correction_active is disabled."""
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("correction_active", True):
        return "corrector_passthrough"
    return "correctors"


def route_after_validation(state: PipelineState, config=None) -> str:
    """If validation failed → END. If incomplete information → END.
    If evaluation off → END. Otherwise → approver."""
    if state.get("validation_error"):
        return "end"
    if state.get("decision") == "INCOMPLETE_INFORMATION":
        return "end"
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("evaluation_active", True):
        return "end"
    return "approver"


def route_after_approver(state: PipelineState) -> str:
    """APPROVED → END. REJECTED → diagnostician. STUCK → END."""
    i = state["iteration"]
    approval = state["output_approver"][i]
    if approval["decision"] == "APPROVED":
        return END
    if approval["decision"] == "STUCK":
        return END
    return "diagnostician"


def route_after_diagnostician(state: PipelineState) -> str:
    """FIX → fix scheduler. STUCK or max iterations → END."""
    i = state["iteration"]
    diagnosis = state["output_diagnostician"][i]
    if diagnosis["decision"] == "STUCK" or i >= 1:  # max 2 iterations (0 and 1)
        return END
    return "fix_scheduler"
