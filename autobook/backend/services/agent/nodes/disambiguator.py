"""Agent 0 — Disambiguator node.

Analyzes transaction for ambiguity. Resolves what it can using context and tools.
Flags unresolved ambiguities with clarification questions.
If any ambiguity is unresolved, sets decision=INCOMPLETE_INFORMATION and pipeline stops early.
Output: DisambiguatorOutput {"ambiguities": [...]}
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
    """Detect and resolve ambiguity in transaction text."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_disambiguator", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_disambiguator") == COMPLETE:
        history.append(history[i - 1])
        return {"output_disambiguator": history, "status_disambiguator": COMPLETE}

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_disambiguator")

    # ── Protect unresolved ambiguities from fix context that resolves them
    prev = history[-1] if history else None
    has_unresolved = prev and any(
        not a.get("resolved") for a in (prev.get("ambiguities") or [])
    )
    fix_ctx = None if has_unresolved else (state.get("fix_context_disambiguator") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(DISAMBIGUATOR, config).with_structured_output(DisambiguatorOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    # ── Advisory only — do not set pipeline decision ──────────────
    update = {
        "output_disambiguator": history,
        "rag_cache_disambiguator": rag_examples,
        "status_disambiguator": COMPLETE,
    }

    return update
