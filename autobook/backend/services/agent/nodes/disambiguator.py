"""Agent 0 — Disambiguator node.

Optional agent that resolves ambiguous transactions using user context.
Output: DisambiguatorOutput {"enriched_text": str, "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, DISAMBIGUATOR, COMPLETE,
)
from services.agent.prompts.disambiguator import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DisambiguatorOutput
from accounting_engine.tools import vendor_history_lookup


def disambiguator_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Resolve ambiguous transaction text using business context."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_disambiguator", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_disambiguator") == COMPLETE:
        history.append(history[i - 1])
        return {"output_disambiguator": history, "status_disambiguator": COMPLETE}

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_disambiguator")
    fix_ctx = (state.get("fix_context_disambiguator") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(DISAMBIGUATOR, config).with_structured_output(DisambiguatorOutput)
    result = structured_llm.invoke(messages)
    history.append(result.model_dump())

    # ── Return state update ───────────────────────────────────────
    return {
        "output_disambiguator": history,
        "rag_cache_disambiguator": rag_examples,
        "status_disambiguator": COMPLETE,
    }
