"""Complexity Detector node.

Flags transactions that exceed LLM capability or knowledge.
Output: ComplexityDetectorOutput {flags: [...]}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, COMPLEXITY_DETECTOR, COMPLETE
from services.agent.prompts.complexity_detector import build_prompt
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import ComplexityDetectorOutput


def complexity_detector_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Detect transactions beyond LLM capability."""
    i = state["iteration"]
    history = list(state.get("output_complexity_detector", []))

    if state.get("status_complexity_detector") == COMPLETE:
        history.append(history[i - 1])
        return {"output_complexity_detector": history, "status_complexity_detector": COMPLETE}

    messages = build_prompt(state)
    structured_llm = get_llm(COMPLEXITY_DETECTOR, config).with_structured_output(ComplexityDetectorOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    return {
        "output_complexity_detector": history,
        "status_complexity_detector": COMPLETE,
    }
