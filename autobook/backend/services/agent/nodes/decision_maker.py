"""Decision Maker node.

Reviews all upstream outputs. Can override classifications.
Only runs when ambiguity or complexity is flagged.
Output: DecisionMakerOutput {decision: proceed|missing_info|llm_stuck, ...}
"""
from langchain_core.runnables import RunnableConfig

from services.agent.graph.state import PipelineState, DECISION_MAKER, COMPLETE
from services.agent.prompts.decision_maker import build_prompt
from services.agent.utils.llm import get_llm
from services.agent.utils.parsers.json_output import DecisionMakerOutput


def decision_maker_node(state: PipelineState, config: RunnableConfig) -> dict:
    """Review upstream outputs and decide: proceed, missing_info, or llm_stuck."""
    i = state["iteration"]
    history = list(state.get("output_decision_maker", []))

    if state.get("status_decision_maker") == COMPLETE:
        history.append(history[i - 1])
        return {"output_decision_maker": history, "status_decision_maker": COMPLETE}

    messages = build_prompt(state)
    structured_llm = get_llm(DECISION_MAKER, config).with_structured_output(DecisionMakerOutput)
    result = structured_llm.invoke(messages)
    output = result.model_dump()
    history.append(output)

    update = {
        "output_decision_maker": history,
        "status_decision_maker": COMPLETE,
    }

    if output["decision"] == "missing_info":
        update["decision"] = "INCOMPLETE_INFORMATION"
        if output.get("clarification_questions"):
            update["clarification_questions"] = output["clarification_questions"]
    elif output["decision"] == "llm_stuck":
        update["decision"] = "STUCK"
        if output.get("stuck_reason"):
            update["stuck_reason"] = output["stuck_reason"]

    return update
