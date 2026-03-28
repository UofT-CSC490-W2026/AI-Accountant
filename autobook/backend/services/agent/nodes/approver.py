"""Agent 6 — Approver node.

Judges whether the journal entry is correct.
Always runs — no status skip. Must re-evaluate after every fix loop.
Output: ApproverOutput {"decision": APPROVED|REJECTED|STUCK,
                         "confidence": VERY_CONFIDENT|...|VERY_UNCERTAIN,
                         "reason": str}
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
    """Judge journal entry correctness and output pipeline decision."""
    # ── Iteration + history ───────────────────────────────────────
    i = state["iteration"]
    history = list(state.get("output_approver", []))

    # ── No skip — approver always re-evaluates ────────────────────

    # ── RAG retrieval ─────────────────────────────────────────────
    rag_examples = retrieve_transaction_examples(state, "rag_cache_approver")
    fix_ctx = (state.get("fix_context_approver") or [None])[-1]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(APPROVER, config).with_structured_output(ApproverOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    # ── Map approver decision to pipeline decision ────────────────
    update = {
        "output_approver": history,
        "rag_cache_approver": rag_examples,
        "status_approver": COMPLETE,
    }

    if output["decision"] == "APPROVED":
        update["decision"] = "APPROVED"
    elif output["decision"] == "STUCK":
        update["decision"] = "STUCK"
        update["stuck_reason"] = output["reason"]
    # REJECTED → diagnostician handles it (no pipeline decision yet)

    return update
