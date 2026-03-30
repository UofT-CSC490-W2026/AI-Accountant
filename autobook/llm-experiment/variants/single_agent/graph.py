"""Single agent variant graph — one LLM call does everything.

Classifies debit/credit structure AND builds journal entry in one shot.
Maps output to PipelineState format for compatible metric collection.
"""
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from services.agent.graph.state import PipelineState, COMPLETE
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DEBIT_SLOTS, CREDIT_SLOTS


# ── Pydantic output schema ───────────────────────────────────────────────

class JournalLine(BaseModel):
    type: Literal["debit", "credit"]
    account_name: str
    amount: float


class JournalEntry(BaseModel):
    reason: str = Field(description="Why these specific accounts were chosen and how amounts were determined from the transaction text")
    lines: list[JournalLine]


_SLOT_DESC = "What items belong in this slot and why this count"


class SingleAgentOutput(BaseModel):
    # 1. Reasoning
    reason: str = Field(description="Overall reasoning about the transaction")

    # 2. Debit structure (6 slots, flattened)
    debit_asset_increase_reason: str = Field(description=_SLOT_DESC)
    debit_asset_increase_count: int
    debit_dividend_increase_reason: str = Field(description=_SLOT_DESC)
    debit_dividend_increase_count: int
    debit_expense_increase_reason: str = Field(description=_SLOT_DESC)
    debit_expense_increase_count: int
    debit_liability_decrease_reason: str = Field(description=_SLOT_DESC)
    debit_liability_decrease_count: int
    debit_equity_decrease_reason: str = Field(description=_SLOT_DESC)
    debit_equity_decrease_count: int
    debit_revenue_decrease_reason: str = Field(description=_SLOT_DESC)
    debit_revenue_decrease_count: int

    # 3. Credit structure (6 slots, flattened)
    credit_liability_increase_reason: str = Field(description=_SLOT_DESC)
    credit_liability_increase_count: int
    credit_equity_increase_reason: str = Field(description=_SLOT_DESC)
    credit_equity_increase_count: int
    credit_revenue_increase_reason: str = Field(description=_SLOT_DESC)
    credit_revenue_increase_count: int
    credit_asset_decrease_reason: str = Field(description=_SLOT_DESC)
    credit_asset_decrease_count: int
    credit_dividend_decrease_reason: str = Field(description=_SLOT_DESC)
    credit_dividend_decrease_count: int
    credit_expense_decrease_reason: str = Field(description=_SLOT_DESC)
    credit_expense_decrease_count: int

    # 4. Entry
    journal_entry: JournalEntry | None

    # 5. Decision
    decision: Literal["APPROVED", "INCOMPLETE_INFORMATION", "STUCK"]
    clarification_questions: list[str] | None = None
    stuck_reason: str | None = None


# ── Node ──────────────────────────────────────────────────────────────────

def single_agent_node(state: PipelineState, config: RunnableConfig) -> dict:
    """One LLM call: classify + build entry."""
    from variants.single_agent.prompt import build_prompt

    i = state["iteration"]

    # ── Build prompt + call LLM ───────────────────────────────────
    messages = build_prompt(state, rag_examples=[])
    structured_llm = get_llm("entry_builder", config).with_structured_output(SingleAgentOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()

    # ── Extract tuples from flattened slots ──────────────────────
    debit_tuple = [output[f"debit_{s}_count"] for s in DEBIT_SLOTS]
    credit_tuple = [output[f"credit_{s}_count"] for s in CREDIT_SLOTS]

    # ── Map to PipelineState format ───────────────────────────────
    debit_history = list(state.get("output_debit_classifier", []))
    credit_history = list(state.get("output_credit_classifier", []))
    entry_history = list(state.get("output_entry_builder", []))

    debit_history.append({"tuple": debit_tuple, "reason": output["reason"]})
    credit_history.append({"tuple": credit_tuple, "reason": output["reason"]})
    entry_history.append(output.get("journal_entry"))

    update = {
        "output_debit_classifier": debit_history,
        "output_credit_classifier": credit_history,
        "output_debit_corrector": debit_history,   # copy for uniform extraction
        "output_credit_corrector": credit_history,  # copy for uniform extraction
        "output_entry_builder": entry_history,
        "status_debit_classifier": COMPLETE,
        "status_credit_classifier": COMPLETE,
        "status_debit_corrector": COMPLETE,
        "status_credit_corrector": COMPLETE,
        "status_entry_builder": COMPLETE,
        "decision": output.get("decision"),
    }
    if output.get("clarification_questions"):
        update["clarification_questions"] = output["clarification_questions"]
    if output.get("stuck_reason"):
        update["stuck_reason"] = output["stuck_reason"]
    return update


# ── Build graph ───────────────────────────────────────────────────────────

builder = StateGraph(PipelineState)
builder.add_node("single_agent", single_agent_node, retry=RetryPolicy(max_attempts=3))
builder.add_edge("__start__", "single_agent")
builder.add_edge("single_agent", END)

app = builder.compile()
