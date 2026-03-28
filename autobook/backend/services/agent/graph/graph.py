"""Full agent pipeline graph.

Single flat StateGraph wiring all 8 agent nodes + validation + fix scheduler
+ ablation routing. No subgraphs — single shared PipelineState.

All ablation is graph-level — nodes are pure (no config checks inside nodes).
Ablation flags: disambiguator_active, correction_pass, evaluation_active.

Pipeline decisions: CONFIDENT / INCOMPLETE_INFORMATION / STUCK
- Disambiguator can stop early with INCOMPLETE_INFORMATION
- Drafter sets decision when it's the terminal agent (evaluation off)
- Approver sets decision when evaluation is on (APPROVED→CONFIDENT, STUCK→STUCK)
- Diagnostician sets STUCK when fix loop fails

Flow (happy path, all features on):
  START → [disambiguator] → debit_classifier ‖ credit_classifier
        → debit_corrector ‖ credit_corrector → entry_builder
        → validation → approver → END

Flow (disambiguator finds ambiguity):
  START → disambiguator → END (INCOMPLETE_INFORMATION)

Flow (correction off):
  ... → classifiers → corrector_passthrough → entry_builder → ...

Flow (evaluation off):
  ... → validation → END (drafter's decision is final)

Flow (fix loop):
  ... → approver (REJECTED) → diagnostician → fix_scheduler
      → [cycle back to disambiguator] → ... → approver (re-eval)
"""
from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy

from services.agent.graph.state import PipelineState

# ── LLM agent nodes ──────────────────────────────────────────────────────
from services.agent.nodes.disambiguator import disambiguator_node
from services.agent.nodes.debit_classifier import debit_classifier_node
from services.agent.nodes.credit_classifier import credit_classifier_node
from services.agent.nodes.debit_corrector import debit_corrector_node
from services.agent.nodes.credit_corrector import credit_corrector_node
from services.agent.nodes.entry_builder import entry_builder_node
from services.agent.nodes.approver import approver_node
from services.agent.nodes.diagnostician import diagnostician_node

# ── Non-LLM nodes ────────────────────────────────────────────────────────
from services.agent.nodes.non_llm import (
    validation_node, fix_scheduler_node,
    corrector_passthrough_node,
)

# ── Routers (all ablation logic lives here) ───────────────────────────────
from services.agent.graph.routers import (
    route_after_start,
    route_after_disambiguator,
    route_before_correctors,
    route_after_validation,
    route_after_approver,
    route_after_diagnostician,
)


# ── Retry policy for LLM nodes ───────────────────────────────────────────
_RETRY = RetryPolicy(max_attempts=3)


# ── Build graph ───────────────────────────────────────────────────────────

builder = StateGraph(PipelineState)

# ── Add nodes ─────────────────────────────────────────────────────────────
builder.add_node("disambiguator", disambiguator_node, retry=_RETRY)
builder.add_node("debit_classifier", debit_classifier_node, retry=_RETRY)
builder.add_node("credit_classifier", credit_classifier_node, retry=_RETRY)
builder.add_node("debit_corrector", debit_corrector_node, retry=_RETRY)
builder.add_node("credit_corrector", credit_corrector_node, retry=_RETRY)
builder.add_node("corrector_passthrough", corrector_passthrough_node)
builder.add_node("entry_builder", entry_builder_node, retry=_RETRY)
builder.add_node("validation", validation_node)
builder.add_node("approver", approver_node, retry=_RETRY)
builder.add_node("diagnostician", diagnostician_node, retry=_RETRY)
builder.add_node("fix_scheduler", fix_scheduler_node)

# ── Edges: START → disambiguator or classifiers (ablation) ────────────────
builder.add_conditional_edges("__start__", route_after_start, {
    "disambiguator": "disambiguator",
    "debit_classifier": "debit_classifier",
    "credit_classifier": "credit_classifier",
})

# ── Edges: disambiguator → both classifiers (always, disambiguator is advisory)
builder.add_conditional_edges("disambiguator", route_after_disambiguator, {
    "debit_classifier": "debit_classifier",
    "credit_classifier": "credit_classifier",
})

# ── Edges: classifiers → correctors or passthrough (ablation) ─────────────
builder.add_conditional_edges("debit_classifier", route_before_correctors, {
    "correctors": "debit_corrector",
    "corrector_passthrough": "corrector_passthrough",
})
builder.add_conditional_edges("credit_classifier", route_before_correctors, {
    "correctors": "credit_corrector",
    "corrector_passthrough": "corrector_passthrough",
})

# ── Edges: correctors / passthrough → entry builder (fan-in) ─────────────
builder.add_edge("debit_corrector", "entry_builder")
builder.add_edge("credit_corrector", "entry_builder")
builder.add_edge("corrector_passthrough", "entry_builder")

# ── Edges: entry builder → validation ─────────────────────────────────────
builder.add_edge("entry_builder", "validation")

# ── Edges: validation → approver or END ───────────────────────────────────
builder.add_conditional_edges("validation", route_after_validation, {
    "approver": "approver",
    "end": END,
})

# ── Edges: approver → END or diagnostician ────────────────────────────────
builder.add_conditional_edges("approver", route_after_approver, {
    END: END,
    "diagnostician": "diagnostician",
})

# ── Edges: diagnostician → fix scheduler or END ──────────────────────────
builder.add_conditional_edges("diagnostician", route_after_diagnostician, {
    "fix_scheduler": "fix_scheduler",
    END: END,
})

# ── Edges: fix scheduler → cycle back ────────────────────────────────────
builder.add_conditional_edges("fix_scheduler", route_after_start, {
    "disambiguator": "disambiguator",
    "debit_classifier": "debit_classifier",
    "credit_classifier": "credit_classifier",
})

# ── Compile ───────────────────────────────────────────────────────────────
app = builder.compile()
