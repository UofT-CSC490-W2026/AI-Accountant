"""Agent 2 — Credit Classifier node.

Classifies credit-side journal lines into 6 directional slots.
Each line gets a reason and IFRS taxonomy category.
Output: CreditClassifierOutput with list[ClassifiedLine] per slot.
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, CREDIT_CLASSIFIER, COMPLETE,
)
from services.agent.prompts.credit_classifier import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm, invoke_structured
from services.agent.utils.parsers.json_output import CreditClassifierOutput, extract_credit_tuple


def credit_classifier_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Classify credit lines into per-slot directional categories."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_credit_classifier", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_credit_classifier") == COMPLETE:
        history.append(history[i - 1])
        return {"output_credit_classifier": history, "status_credit_classifier": COMPLETE}

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_credit_classifier")
    fix_ctx = (state.get("fix_context_credit_classifier") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    output = invoke_structured(get_llm(CREDIT_CLASSIFIER, config), CreditClassifierOutput, messages)

    # ── Add tuple for downstream compatibility ────────────────────
    output["tuple"] = list(extract_credit_tuple(output))

    history.append(output)

    # ── Return state update ───────────────────────────────────────
    return {
        "output_credit_classifier": history,
        "rag_cache_credit_classifier": rag_examples,
        "status_credit_classifier": COMPLETE,
    }
