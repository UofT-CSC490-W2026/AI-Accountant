"""Agent 1 — Debit Classifier node.

Classifies debit-side journal lines into 6 directional slots.
Each line gets a reason and IFRS taxonomy category.
Output: DebitClassifierOutput with list[ClassifiedLine] per slot.
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, DEBIT_CLASSIFIER, COMPLETE,
)
from services.agent.prompts.debit_classifier import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm, invoke_structured
from services.agent.utils.parsers.json_output import DebitClassifierOutput, extract_debit_tuple


def debit_classifier_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Classify debit lines into per-slot directional categories."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_debit_classifier", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_debit_classifier") == COMPLETE:
        history.append(history[i - 1])
        return {"output_debit_classifier": history, "status_debit_classifier": COMPLETE}

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_debit_classifier")
    fix_ctx = (state.get("fix_context_debit_classifier") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    output = invoke_structured(get_llm(DEBIT_CLASSIFIER, config), DebitClassifierOutput, messages)

    # ── Add tuple for downstream compatibility ────────────────────
    output["tuple"] = list(extract_debit_tuple(output))

    history.append(output)

    # ── Return state update ───────────────────────────────────────
    return {
        "output_debit_classifier": history,
        "rag_cache_debit_classifier": rag_examples,
        "status_debit_classifier": COMPLETE,
    }
