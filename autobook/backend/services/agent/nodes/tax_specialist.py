"""Tax Specialist node.

Determines tax treatment from transaction text.
Output: TaxSpecialistOutput {reasoning, tax_mentioned, taxable, ...}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, TAX_SPECIALIST, COMPLETE
from services.agent.prompts.tax_specialist import build_prompt
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import TaxSpecialistOutput


def tax_specialist_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Determine tax treatment for the transaction."""
    i = state["iteration"]
    history = list(state.get("output_tax_specialist", []))

    if state.get("status_tax_specialist") == COMPLETE:
        history.append(history[i - 1])
        return {"output_tax_specialist": history, "status_tax_specialist": COMPLETE}

    messages = build_prompt(state)
    structured_llm = get_llm(TAX_SPECIALIST, config).with_structured_output(TaxSpecialistOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    return {
        "output_tax_specialist": history,
        "status_tax_specialist": COMPLETE,
    }
