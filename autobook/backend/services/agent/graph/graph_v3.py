"""V3 agent pipeline graph.

Specialized agents with 2-layer routing:
  Layer 1 (parallel): ambiguity_detector, complexity_detector,
                      debit_classifier, credit_classifier, tax_specialist
  Layer 2 (conditional):
    - If all clear → entry_drafter → END
    - If flagged → decision_maker → entry_drafter or END

Pipeline decisions: APPROVED / INCOMPLETE_INFORMATION / STUCK
"""
from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from services.agent.graph.state import PipelineState

# ── Layer 1 nodes ─────────────────────────────────────────────────────────
from services.agent.nodes.ambiguity_detector import ambiguity_detector_node
from services.agent.nodes.complexity_detector import complexity_detector_node
from services.agent.nodes.debit_classifier import debit_classifier_node
from services.agent.nodes.credit_classifier import credit_classifier_node
from services.agent.nodes.tax_specialist import tax_specialist_node

# ── Layer 2 nodes ─────────────────────────────────────────────────────────
from services.agent.nodes.decision_maker import decision_maker_node
from services.agent.nodes.entry_drafter import entry_drafter_node
from services.agent.nodes.non_llm.merge_lines import merge_lines_node


# ── Retry policy ──────────────────────────────────────────────────────────
_RETRY = RetryPolicy(max_attempts=3)


# ── Routers ───────────────────────────────────────────────────────────────

def route_layer1_start(state: PipelineState) -> list[str]:
    """Fan out to all 5 layer 1 agents in parallel."""
    return [
        "ambiguity_detector",
        "complexity_detector",
        "debit_classifier",
        "credit_classifier",
        "tax_specialist",
    ]


def route_after_layer1(state: PipelineState) -> str:
    """Route based on ambiguity and complexity flags."""
    # Check ambiguity detector
    ambiguity = (state.get("output_ambiguity_detector") or [None])[-1]
    has_unresolved = False
    if ambiguity:
        ambiguities = ambiguity.get("ambiguities", [])
        has_unresolved = any(not a.get("resolved", True) for a in ambiguities)

    # Check complexity detector
    complexity = (state.get("output_complexity_detector") or [None])[-1]
    has_skeptical = False
    if complexity:
        flags = complexity.get("flags", [])
        has_skeptical = any(f.get("skeptical", False) for f in flags)

    if has_unresolved or has_skeptical:
        return "decision_maker"
    return "entry_drafter"


def route_after_decision(state: PipelineState) -> str:
    """Route based on decision maker output."""
    decision_maker = (state.get("output_decision_maker") or [None])[-1]
    if decision_maker and decision_maker.get("decision") == "proceed":
        return "entry_drafter"
    return "end"


# ── Build graph ───────────────────────────────────────────────────────────

builder = StateGraph(PipelineState)

# ── Layer 1 nodes ─────────────────────────────────────────────────────────
builder.add_node("ambiguity_detector", ambiguity_detector_node, retry=_RETRY)
builder.add_node("complexity_detector", complexity_detector_node, retry=_RETRY)
builder.add_node("debit_classifier", debit_classifier_node, retry=_RETRY)
builder.add_node("credit_classifier", credit_classifier_node, retry=_RETRY)
builder.add_node("tax_specialist", tax_specialist_node, retry=_RETRY)

# ── Layer 2 nodes ─────────────────────────────────────────────────────────
builder.add_node("decision_maker", decision_maker_node, retry=_RETRY)
builder.add_node("entry_drafter", entry_drafter_node, retry=_RETRY)

# ── Edges: START → all 5 layer 1 agents (parallel fan-out) ───────────────
builder.add_conditional_edges("__start__", route_layer1_start, {
    "ambiguity_detector": "ambiguity_detector",
    "complexity_detector": "complexity_detector",
    "debit_classifier": "debit_classifier",
    "credit_classifier": "credit_classifier",
    "tax_specialist": "tax_specialist",
})

# ── Edges: all 5 layer 1 → join point (conditional routing) ──────────────
# LangGraph automatically waits for all upstream nodes before running the
# conditional edge. We need all 5 to point to the same routing function.
# Use a "layer1_join" passthrough node as the convergence point.

def layer1_join_node(state: PipelineState) -> dict:
    """No-op join point. All layer 1 agents must complete before this runs."""
    return {}

builder.add_node("layer1_join", layer1_join_node)

builder.add_edge("ambiguity_detector", "layer1_join")
builder.add_edge("complexity_detector", "layer1_join")
builder.add_edge("debit_classifier", "layer1_join")
builder.add_edge("credit_classifier", "layer1_join")
builder.add_edge("tax_specialist", "layer1_join")

# ── Edges: join → decision_maker or entry_drafter ─────────────────────────
builder.add_conditional_edges("layer1_join", route_after_layer1, {
    "decision_maker": "decision_maker",
    "entry_drafter": "entry_drafter",
})

# ── Edges: decision_maker → entry_drafter or END ─────────────────────────
builder.add_conditional_edges("decision_maker", route_after_decision, {
    "entry_drafter": "entry_drafter",
    "end": END,
})

# ── Edges: entry_drafter → merge_lines → END ─────────────────────────────
builder.add_node("merge_lines", merge_lines_node)
builder.add_edge("entry_drafter", "merge_lines")
builder.add_edge("merge_lines", END)

# ── Compile ───────────────────────────────────────────────────────────────
app = builder.compile()
