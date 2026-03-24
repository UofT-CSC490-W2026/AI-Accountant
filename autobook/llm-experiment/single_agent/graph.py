"""Single agent variant graph — one LLM call does everything.

Classifies debit/credit tuples AND builds journal entry in one shot.
Maps output to PipelineState format for compatible metric collection.
"""
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from services.agent.graph.state import PipelineState, COMPLETE
from services.agent.utils.llm import get_llm


# ── Pydantic output schema ───────────────────────────────────────────────

class JournalLine(BaseModel):
    account_name: str
    type: Literal["debit", "credit"]
    amount: float


class JournalEntry(BaseModel):
    date: str
    description: str
    rationale: str
    lines: list[JournalLine]


class SingleAgentOutput(BaseModel):
    debit_tuple: tuple[int, int, int, int, int, int]
    credit_tuple: tuple[int, int, int, int, int, int]
    journal_entry: JournalEntry | None
    reason: str


# ── Node ──────────────────────────────────────────────────────────────────

def single_agent_node(state: PipelineState, config: RunnableConfig) -> dict:
    """One LLM call: classify + build entry."""
    from llm_experiment.single_agent.prompt import build_prompt

    i = state["iteration"]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples=[])
    structured_llm = get_llm("entry_builder", config).with_structured_output(SingleAgentOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()

    # ── Map to PipelineState format ───────────────────────────────
    debit_history = list(state.get("output_debit_classifier", []))
    credit_history = list(state.get("output_credit_classifier", []))
    entry_history = list(state.get("output_entry_builder", []))

    debit_history.append({"tuple": list(output["debit_tuple"]), "reason": output["reason"]})
    credit_history.append({"tuple": list(output["credit_tuple"]), "reason": output["reason"]})
    entry_history.append(output.get("journal_entry"))

    return {
        "output_debit_classifier": debit_history,
        "output_credit_classifier": credit_history,
        "output_debit_corrector": debit_history,   # copy for uniform extraction
        "output_credit_corrector": credit_history,  # copy for uniform extraction
        "output_entry_builder": entry_history,
        "output_approver": [{"approved": True, "confidence": 1.0, "reason": "single agent — no evaluator"}],
        "status_debit_classifier": COMPLETE,
        "status_credit_classifier": COMPLETE,
        "status_debit_corrector": COMPLETE,
        "status_credit_corrector": COMPLETE,
        "status_entry_builder": COMPLETE,
        "status_approver": COMPLETE,
        "route": "post",
    }


# ── Build graph ───────────────────────────────────────────────────────────

builder = StateGraph(PipelineState)
builder.add_node("single_agent", single_agent_node, retry=RetryPolicy(max_attempts=3))
builder.add_edge("__start__", "single_agent")
builder.add_edge("single_agent", END)

app = builder.compile()
