"""Agent 6 — Approver node.

Judges whether the journal entry is correct.
Always runs (no status skip — must re-evaluate after any fix).
Output: ApproverOutput {"approved": bool, "confidence": float, "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, APPROVER, COMPLETE,
)
from services.agent.prompts.approver import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import ApproverOutput


def approver_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_approver", []))

    # Approver always runs — no status skip.
    # It must re-evaluate the journal entry after every fix loop.
    rag_examples = retrieve_transaction_examples(state, "rag_cache_approver")
    fix_ctx = (state.get("fix_context_approver") or [None])[-1]

    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(APPROVER, config).with_structured_output(ApproverOutput)
    result = structured_llm.invoke(messages)
    history.append(result.model_dump())

    return {
        "output_approver": history,
        "rag_cache_approver": rag_examples,
        "status_approver": COMPLETE,
    }
