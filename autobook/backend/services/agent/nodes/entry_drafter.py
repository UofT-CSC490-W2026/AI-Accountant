"""Entry Drafter node.

Simple composer. Trusts upstream classifications and tax treatment.
Builds the journal entry from debit/credit structure + tax context.
Two-step invocation: optional calculator tool call, then structured output.
Output: EntryDrafterOutput {reason, lines: [...]}
"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, ENTRY_DRAFTER, COMPLETE
from services.agent.prompts.entry_drafter import build_prompt
from services.agent.utils.llm import get_llm
from services.agent.utils.calculator import CALCULATOR_TOOLS, safe_eval
from services.agent.utils.parsers.json_output import EntryDrafterOutput


_CALC_KEYWORDS = {"interest", "discount", "present value", "pv", "annuity",
                   "amortiz", "allocat", "prorate", "apportion", "%", "rate"}


def _needs_calculation(state: PipelineState) -> bool:
    """Check if the transaction likely involves computation."""
    tx = (state.get("transaction_text") or "").lower()
    return any(kw in tx for kw in _CALC_KEYWORDS)


def _run_calculator_step(llm, messages):
    """Pre-computation: let LLM call calculator tool.

    Returns computed values as a string to inject into the final prompt,
    or None on any error.
    """
    try:
        calc_llm = llm.bind_tools(CALCULATOR_TOOLS)
        response = calc_llm.invoke(messages)

        if not response.tool_calls:
            return None

        results = []
        for tc in response.tool_calls:
            expr = tc["args"].get("expression", "")
            value = safe_eval(expr)
            results.append(f"{expr} = {round(value, 2)}")

        return "\n".join(results) if results else None
    except Exception:
        return None


def entry_drafter_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Build journal entry from upstream classifications."""
    i = state["iteration"]
    history = list(state.get("output_entry_drafter", []))

    if state.get("status_entry_drafter") == COMPLETE:
        history.append(history[i - 1])
        return {"output_entry_drafter": history, "status_entry_drafter": COMPLETE}

    messages = build_prompt(state)
    llm = get_llm(ENTRY_DRAFTER, config)

    # Step 1: optional calculator pre-computation (only for math-heavy transactions)
    computed = _run_calculator_step(llm, messages) if _needs_calculation(state) else None
    if computed:
        # Inject computed values as a follow-up user message
        messages.append(
            HumanMessage(content=[{"text": f"<computed_values>\n{computed}\n</computed_values>\nNow build the journal entry using these computed values."}])
        )

    # Step 2: structured output
    structured_llm = llm.with_structured_output(EntryDrafterOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    update = {
        "output_entry_drafter": history,
        "status_entry_drafter": COMPLETE,
    }

    # Set decision to APPROVED if no decision_maker ran (confident mode)
    if not state.get("decision"):
        update["decision"] = "APPROVED"

    return update
