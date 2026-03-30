"""V3 Simple — classifiers + tax + entry drafter only.

No ambiguity detection, no complexity assessment, no decision maker.
Always builds an entry. Never returns INCOMPLETE_INFORMATION.

Flow:
  START → [debit_classifier ‖ credit_classifier ‖ tax_specialist]
        → entry_drafter → merge_lines → END
"""
from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from services.agent.graph.state import PipelineState

from services.agent.nodes.debit_classifier import debit_classifier_node
from services.agent.nodes.credit_classifier import credit_classifier_node
from services.agent.nodes.tax_specialist import tax_specialist_node
from services.agent.nodes.entry_drafter import entry_drafter_node
from services.agent.nodes.non_llm.merge_lines import merge_lines_node

_RETRY = RetryPolicy(max_attempts=3)


def route_start(state: PipelineState) -> list[str]:
    """Fan out to 3 agents in parallel."""
    return ["debit_classifier", "credit_classifier", "tax_specialist"]


builder = StateGraph(PipelineState)

builder.add_node("debit_classifier", debit_classifier_node, retry=_RETRY)
builder.add_node("credit_classifier", credit_classifier_node, retry=_RETRY)
builder.add_node("tax_specialist", tax_specialist_node, retry=_RETRY)
builder.add_node("entry_drafter", entry_drafter_node, retry=_RETRY)
builder.add_node("merge_lines", merge_lines_node)

# START → 3 parallel
builder.add_conditional_edges("__start__", route_start, {
    "debit_classifier": "debit_classifier",
    "credit_classifier": "credit_classifier",
    "tax_specialist": "tax_specialist",
})

# 3 → entry_drafter
builder.add_edge("debit_classifier", "entry_drafter")
builder.add_edge("credit_classifier", "entry_drafter")
builder.add_edge("tax_specialist", "entry_drafter")

# entry_drafter → merge_lines → END
builder.add_edge("entry_drafter", "merge_lines")
builder.add_edge("merge_lines", END)

app = builder.compile()
