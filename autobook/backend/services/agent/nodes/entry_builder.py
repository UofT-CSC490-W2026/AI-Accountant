"""Agent 5 — Entry Builder node.

Constructs complete journal entry from refined tuples + tool results.
Output: EntryBuilderOutput {"date", "description", "rationale", "lines": [...]}
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
from accounting_engine.validators import validate_journal_entry, validate_tax


def entry_builder_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_entry_builder", []))

    if state.get("status_entry_builder") == COMPLETE:
        history.append(history[i - 1])
    else:
        rag_examples = retrieve_transaction_examples(state, "rag_cache_entry_builder")
        fix_ctx = (state.get("fix_context_entry_builder") or [None])[-1]

        # Tool lookups
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

        messages = build_prompt(
            state, rag_examples,
            coa_results=coa_results,
            tax_results=tax_results,
            vendor_results=vendor_results,
            fix_context=fix_ctx,
        )
        structured_llm = get_llm(ENTRY_BUILDER, config).with_structured_output(EntryBuilderOutput)
        result = structured_llm.invoke(messages)
        output = result.model_dump()

        # Validate business rules
        validation = validate_journal_entry(output)
        if not validation["valid"]:
            raise ValueError(f"Journal entry validation failed: {validation['errors']}")

        tax_validation = validate_tax(
            output,
            province=user_ctx.get("province", "ON"),
            tax_rate=tax_results.get("rate", 0.13),
        )
        if not tax_validation["valid"]:
            raise ValueError(f"Tax validation failed: {tax_validation['errors']}")

        history.append(output)

    return {
        "output_entry_builder": history,
        "rag_cache_entry_builder": rag_examples if 'rag_examples' in dir() else state.get("rag_cache_entry_builder", []),
        "status_entry_builder": COMPLETE,
    }
