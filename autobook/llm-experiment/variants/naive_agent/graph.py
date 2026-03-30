"""Naive single agent graph — same schema as single_agent, different prompt.

Reuses SingleAgentOutput for compatible metric collection.
"""
from langgraph.graph import StateGraph, END
from langgraph.types import RetryPolicy
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, COMPLETE
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DEBIT_SLOTS, CREDIT_SLOTS
from variants.single_agent.graph import SingleAgentOutput


def naive_agent_node(state: PipelineState, config: RunnableConfig) -> dict:
    """One LLM call with naive prompt: classify + build entry."""
    from variants.naive_agent.prompt import build_prompt

    i = state["iteration"]

    messages = build_prompt(state, rag_examples=[])
    structured_llm = get_llm("entry_builder", config).with_structured_output(SingleAgentOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()

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


builder = StateGraph(PipelineState)
builder.add_node("single_agent", naive_agent_node, retry=RetryPolicy(max_attempts=3))
builder.add_edge("__start__", "single_agent")
builder.add_edge("single_agent", END)

app = builder.compile()
