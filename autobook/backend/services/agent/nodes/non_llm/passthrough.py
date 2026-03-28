"""Corrector passthrough node — used when correction_pass is disabled.

Copies classifier output to corrector output fields so entry builder
reads from the same place regardless of whether correction ran.
No LLM call, no logic — just data mapping.
"""
from services.agent.graph.state import PipelineState, COMPLETE


def corrector_passthrough_node(state: PipelineState) -> dict:
    """Copy classifier outputs to corrector output fields."""
    i = state["iteration"]

    debit_history = list(state.get("output_debit_corrector", []))
    credit_history = list(state.get("output_credit_corrector", []))

    debit_history.append(state["output_debit_classifier"][i])
    credit_history.append(state["output_credit_classifier"][i])

    return {
        "output_debit_corrector": debit_history,
        "output_credit_corrector": credit_history,
        "status_debit_corrector": COMPLETE,
        "status_credit_corrector": COMPLETE,
    }
