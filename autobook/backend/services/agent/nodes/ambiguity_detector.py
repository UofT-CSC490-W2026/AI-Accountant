"""Ambiguity Detector node.

Flags missing business facts that would change the journal entry structure.
Output: AmbiguityDetectorOutput {ambiguities: [...]}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, AMBIGUITY_DETECTOR, COMPLETE
from services.agent.prompts.disambiguator import build_prompt
from services.agent.rag.transaction import retrieve_transaction_examples
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import AmbiguityDetectorOutput


def ambiguity_detector_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Detect missing business facts in transaction text."""
    i = state["iteration"]
    history = list(state.get("output_ambiguity_detector", []))

    if state.get("status_ambiguity_detector") == COMPLETE:
        history.append(history[i - 1])
        return {"output_ambiguity_detector": history, "status_ambiguity_detector": COMPLETE}

    rag_examples = retrieve_transaction_examples(state, "rag_cache_disambiguator")

    messages = build_prompt(state, rag_examples)
    structured_llm = get_llm(AMBIGUITY_DETECTOR, config).with_structured_output(AmbiguityDetectorOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    # Also write to legacy key for backward compatibility
    return {
        "output_ambiguity_detector": history,
        "output_disambiguator": history,
        "status_ambiguity_detector": COMPLETE,
        "status_disambiguator": COMPLETE,
    }
