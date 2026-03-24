"""Agent 3 — Debit Corrector node.

Cross-validates debit tuple using credit side. Fixes misclassifications.
Output: DebitCorrectorOutput {"tuple": [int*6], "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, DEBIT_CORRECTOR, COMPLETE,
)
from services.agent.prompts.debit_corrector import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.rag.correction import retrieve_correction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DebitCorrectorOutput


def debit_corrector_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Re-evaluate debit tuple using credit side as cross-validation."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_debit_corrector", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_debit_corrector") == COMPLETE:
        history.append(history[i - 1])
        return {"output_debit_corrector": history, "status_debit_corrector": COMPLETE}

    # ── Ablation check — pass through classifier output if off ────
    configurable = (config or {}).get("configurable", {})
    if not configurable.get("correction_pass", True):
        classifier_output = state["output_debit_classifier"][i]
        history.append({"tuple": classifier_output["tuple"], "reason": "correction pass disabled"})
        return {"output_debit_corrector": history, "status_debit_corrector": COMPLETE}

    # ── RAG retrieval (transaction on first run, corrections on rerun)
    cache_key = "rag_cache_debit_corrector"
    if i == 0:
        rag_examples = retrieve_transaction_examples(state, cache_key)
    else:
        rag_examples = retrieve_correction_examples(state, cache_key)

    fix_ctx = (state.get("fix_context_debit_corrector") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(DEBIT_CORRECTOR, config).with_structured_output(DebitCorrectorOutput)
    result = structured_llm.invoke(messages)
    history.append(result.model_dump())

    # ── Return state update ───────────────────────────────────────
    return {
        "output_debit_corrector": history,
        "rag_cache_debit_corrector": rag_examples,
        "status_debit_corrector": COMPLETE,
    }
