"""Agent 5 — Entry Builder node.

Constructs complete journal entry from refined tuples + tool results.
When it's the terminal decision-maker (no approver), also outputs the
pipeline decision: CONFIDENT, INCOMPLETE_INFORMATION, or STUCK.
Output: EntryBuilderOutput {"date", "description", "rationale", "lines", ...}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, ENTRY_BUILDER, COMPLETE,
)
from services.agent.prompts.entry_builder import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import EntryBuilderOutput
from accounting_engine.tools import coa_lookup, tax_rules_lookup, vendor_history_lookup


def entry_builder_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Build complete journal entry from tuples, tools, and transaction text."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_entry_builder", []))

    # ── Skip if complete (copy previous for alignment) ────────────
    if state.get("status_entry_builder") == COMPLETE:
        history.append(history[i - 1])
        return {"output_entry_builder": history, "status_entry_builder": COMPLETE}

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_entry_builder")
    fix_ctx = (state.get("fix_context_entry_builder") or [None])[-1]

    # ── Tool lookups ──────────────────────────────────────────────
    user_ctx = state.get("user_context", {})
    coa_results = coa_lookup(
        user_id=user_ctx.get("user_id", ""),
    )
    tax_results = tax_rules_lookup(
        province=user_ctx.get("province", "ON"),
        transaction_type="general",
    )
    vendor_results = vendor_history_lookup(
        user_id=user_ctx.get("user_id", ""),
        vendor_name=state["transaction_text"].split()[0] if state["transaction_text"] else "",
    )

    # ── Read pipeline config ─────────────────────────────────────
    configurable = (config or {}).get("configurable", {})
    pipeline_config = {
        "disambiguator_active": configurable.get("disambiguator_active", True),
        "correction_active": configurable.get("correction_active", True),
        "evaluation_active": configurable.get("evaluation_active", True),
    }

    # ── Disambiguator opinions (if disambiguator ran) ─────────────
    disambiguator_opinions = state.get("output_disambiguator", [])
    has_disambiguator = pipeline_config.get("disambiguator_active", True)

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(
        state, rag_examples,
        coa_results=coa_results,
        tax_results=tax_results,
        vendor_results=vendor_results,
        fix_context=fix_ctx,
        pipeline_config=pipeline_config,
    )
    structured_llm = get_llm(ENTRY_BUILDER, config).with_structured_output(EntryBuilderOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    # ── Return state update ───────────────────────────────────────
    update = {
        "output_entry_builder": history,
        "rag_cache_entry_builder": rag_examples,
        "status_entry_builder": COMPLETE,
    }

    # Enforce INCOMPLETE_INFORMATION if any disambiguator response says "incomplete"
    responses = output.get("disambiguator_responses") or []
    if any(r["action"] == "incomplete" for r in responses):
        output["decision"] = "INCOMPLETE_INFORMATION"

    # Always propagate INCOMPLETE_INFORMATION (entry builder detects missing facts when D=off)
    if output.get("decision") == "INCOMPLETE_INFORMATION":
        update["decision"] = output["decision"]
        if output.get("clarification_questions"):
            update["clarification_questions"] = output["clarification_questions"]
    # Propagate APPROVED/STUCK only when terminal (no approver)
    elif not pipeline_config["evaluation_active"] and output.get("decision"):
        update["decision"] = output["decision"]
        if output.get("stuck_reason"):
            update["stuck_reason"] = output["stuck_reason"]

    return update
