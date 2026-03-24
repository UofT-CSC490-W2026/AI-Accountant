"""Agent 7 — Diagnostician node.

Identifies root cause agent and produces fix plan.
Only called when approver rejects.
Output: DiagnosticianOutput {"decision": "FIX"|"STUCK", "fix_plans": [...], "reason": str}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import (
    PipelineState, DIAGNOSTICIAN, COMPLETE,
)
from services.agent.prompts.diagnostician import build_prompt
from services.agent.rag.fix_history import retrieve_fix_history
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DiagnosticianOutput


def diagnostician_node(state: PipelineState, config: RunnableConfig) -> dict:
    i = state["iteration"]
    history = list(state.get("output_diagnostician", []))

    # Diagnostician always runs when invoked — no status skip.
    # Only called when output_approver[i]["approved"] is False.
    rag_examples = retrieve_fix_history(state)
    fix_ctx = (state.get("fix_context_diagnostician") or [None])[-1]

    messages = build_prompt(state, rag_examples, fix_context=fix_ctx)
    structured_llm = get_llm(DIAGNOSTICIAN, config).with_structured_output(DiagnosticianOutput)
    result = structured_llm.invoke(messages)
    history.append(result.model_dump())

    return {
        "output_diagnostician": history,
        "rag_cache_diagnostician": rag_examples,
        "status_diagnostician": COMPLETE,
    }
