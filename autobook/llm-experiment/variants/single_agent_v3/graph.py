"""Single agent V3 graph — one LLM call with full V3 knowledge + extended schema.

Extended output captures intermediate reasoning (ambiguity, complexity, tax)
for traceability while keeping it to a single LLM call.
"""
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from services.agent.graph.state import PipelineState, COMPLETE
from services.agent.utils.llm import get_llm, invoke_structured
from services.agent.utils.parsers.json_output import DEBIT_SLOTS, CREDIT_SLOTS
from services.agent.rag.transaction import retrieve_transaction_examples


# ── Extended output schema ───────────────────────────────────────────────

class AmbiguityItem(BaseModel):
    aspect: str = Field(description="The ambiguous aspect")
    resolved: bool = Field(description="True if resolved by text, conventions, or context")
    clarification_question: str | None = Field(default=None, description="Question to resolve, if unresolved")

class ComplexityItem(BaseModel):
    aspect: str = Field(description="The assessed aspect")
    skeptical: bool = Field(description="True if beyond LLM capability")

class TaxAssessment(BaseModel):
    tax_mentioned: bool = Field(description="True if transaction text mentions tax")
    add_tax_lines: bool = Field(description="True if entry should include tax lines")
    tax_rate: float | None = Field(default=None, description="Tax rate if mentioned")
    tax_amount: float | None = Field(default=None, description="Tax amount if mentioned")

class JournalLine(BaseModel):
    type: Literal["debit", "credit"]
    account_name: str
    amount: float

class JournalEntry(BaseModel):
    reason: str = Field(description="Why these accounts and amounts")
    lines: list[JournalLine]

_SLOT_DESC = "What items belong in this slot and why this count"

class SingleAgentV3Output(BaseModel):
    # Step 1: Ambiguity
    ambiguities: list[AmbiguityItem] = Field(description="Ambiguities found, resolved and unresolved")

    # Step 2: Complexity
    complexity_flags: list[ComplexityItem] = Field(description="Complexity aspects assessed")

    # Step 3: Classification — debit (6 slots)
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

    # Step 3: Classification — credit (6 slots)
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

    # Step 4: Tax
    tax: TaxAssessment = Field(description="Tax treatment assessment")

    # Step 5: Decision
    decision: Literal["APPROVED", "INCOMPLETE_INFORMATION", "STUCK"]
    decision_rationale: str = Field(description="Why this decision")
    clarification_questions: list[str] | None = None
    stuck_reason: str | None = None

    # Step 6: Entry
    journal_entry: JournalEntry | None

    # Overall reasoning
    reason: str = Field(description="Overall reasoning about the transaction")


# ── Node ─────────────────────────────────────────────────────────────────

def single_agent_v3_node(state: PipelineState, config: RunnableConfig) -> dict:
    """One LLM call with full V3 knowledge: all stages in one pass."""
    from variants.single_agent_v3.prompt import build_prompt

    i = state["iteration"]

    rag_examples = retrieve_transaction_examples(state, "rag_cache_entry_builder")
    messages = build_prompt(state, rag_examples=rag_examples)
    output = invoke_structured(get_llm("entry_builder", config), SingleAgentV3Output, messages)

    debit_tuple = [output[f"debit_{s}_count"] for s in DEBIT_SLOTS]
    credit_tuple = [output[f"credit_{s}_count"] for s in CREDIT_SLOTS]

    debit_history = list(state.get("output_debit_classifier", []))
    credit_history = list(state.get("output_credit_classifier", []))
    entry_history = list(state.get("output_entry_builder", []))

    debit_history.append({"tuple": debit_tuple, "reason": output["reason"]})
    credit_history.append({"tuple": credit_tuple, "reason": output["reason"]})
    entry_history.append(output.get("journal_entry"))

    update = {
        "output_debit_classifier": debit_history,
        "output_credit_classifier": credit_history,
        "output_debit_corrector": debit_history,
        "output_credit_corrector": credit_history,
        "output_entry_builder": entry_history,
        "output_ambiguity_detector": [{"ambiguities": output.get("ambiguities", [])}],
        "output_disambiguator": [{"ambiguities": output.get("ambiguities", [])}],
        "output_complexity_detector": [{"flags": output.get("complexity_flags", [])}],
        "output_tax_specialist": [output.get("tax", {})],
        "status_debit_classifier": COMPLETE,
        "status_credit_classifier": COMPLETE,
        "status_debit_corrector": COMPLETE,
        "status_credit_corrector": COMPLETE,
        "status_entry_builder": COMPLETE,
        "status_ambiguity_detector": COMPLETE,
        "status_disambiguator": COMPLETE,
        "status_complexity_detector": COMPLETE,
        "status_tax_specialist": COMPLETE,
        "decision": output.get("decision"),
    }
    if output.get("clarification_questions"):
        update["clarification_questions"] = output["clarification_questions"]
    if output.get("stuck_reason"):
        update["stuck_reason"] = output["stuck_reason"]
    return update


# ── Build graph ──────────────────────────────────────────────────────────

builder = StateGraph(PipelineState)
builder.add_node("single_agent", single_agent_v3_node, retry=RetryPolicy(max_attempts=3))
builder.add_edge("__start__", "single_agent")
builder.add_edge("single_agent", END)

app = builder.compile()
