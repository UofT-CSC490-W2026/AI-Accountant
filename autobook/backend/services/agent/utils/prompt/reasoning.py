"""Compile the generator reasoning trace from pipeline state.

Formats all iterations' outputs into a labeled timeline.
Used by Approver (Agent 6) and Diagnostician (Agent 7).
"""
from services.agent.graph.state import (
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    PipelineState,
)

_AGENT_LABELS: list[tuple[str, str]] = [
    (f"output_{DISAMBIGUATOR}", "Agent 0 (Disambiguator)"),
    (f"output_{DEBIT_CLASSIFIER}", "Agent 1 (Debit Classifier)"),
    (f"output_{CREDIT_CLASSIFIER}", "Agent 2 (Credit Classifier)"),
    (f"output_{DEBIT_CORRECTOR}", "Agent 3 (Debit Corrector)"),
    (f"output_{CREDIT_CORRECTOR}", "Agent 4 (Credit Corrector)"),
    (f"output_{ENTRY_BUILDER}", "Agent 5 (Entry Builder)"),
]


def compile_reasoning_trace(state: PipelineState, iteration: int) -> str:
    """Compile a labeled reasoning trace from all generator agent outputs.

    Formats all iterations 0..iteration as a timeline.

    Args:
        state: Pipeline state containing output_* list fields.
        iteration: Current iteration index.

    Returns:
        Formatted string with each iteration's agent outputs labeled.
    """
    lines = []
    for i in range(iteration + 1):
        lines.append(f"--- Iteration {i} ---")
        for field, label in _AGENT_LABELS:
            outputs = state.get(field, [])
            if i < len(outputs) and outputs[i] is not None:
                lines.append(f"{label}: {outputs[i]}")
        lines.append("")

    return "\n".join(lines).rstrip()
