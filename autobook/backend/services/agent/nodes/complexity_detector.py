"""Complexity Detector node.

Flags transactions that exceed LLM capability or knowledge.
Output: ComplexityDetectorOutput {flags: [...]}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, COMPLEXITY_DETECTOR, COMPLETE
from services.agent.prompts.complexity_detector import build_prompt
from services.agent.utils.llm import get_llm, invoke_structured
from services.agent.utils.parsers.json_output import ComplexityDetectorOutput


def complexity_detector_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Detect transactions beyond LLM capability."""
    i = state["iteration"]
    history = list(state.get("output_complexity_detector", []))

    if state.get("status_complexity_detector") == COMPLETE:
        history.append(history[i - 1])
        return {"output_complexity_detector": history, "status_complexity_detector": COMPLETE}

    messages = build_prompt(state)
    output = invoke_structured(get_llm(COMPLEXITY_DETECTOR, config), ComplexityDetectorOutput, messages)
    history.append(output)

    return {
        "output_complexity_detector": history,
        "status_complexity_detector": COMPLETE,
    }
