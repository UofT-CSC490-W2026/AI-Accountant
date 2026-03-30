import logging

from langchain_aws import ChatBedrockConverse
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from config import get_settings

logger = logging.getLogger(__name__)

# Per-agent max output tokens — accounts for JSON + reason via tool calling
MAX_TOKENS: dict[str, int] = {
    # V3 agents
    "ambiguity_detector":  2000,
    "complexity_detector": 2000,
    "debit_classifier":    4000,
    "credit_classifier":   4000,
    "tax_specialist":      2000,
    "decision_maker":      4000,
    "entry_drafter":       2000,
    # Legacy agents
    "disambiguator":       2000,
    "debit_corrector":     2000,
    "credit_corrector":    2000,
    "entry_builder":       4000,
    "approver":            2000,
    "diagnostician":       2000,
}


def get_llm(agent_name: str, config: RunnableConfig | None = None) -> ChatBedrockConverse:
    """Return a configured ChatBedrockConverse client for the given agent.

    Args:
        agent_name: One of the 8 agent names (e.g. "debit_classifier").
        config: LangGraph RunnableConfig — experiment runner passes model/thinking
                overrides via config["configurable"]. Production passes nothing.

    Returns:
        Configured ChatBedrockConverse instance.
    """
    settings = get_settings()
    configurable = (config or {}).get("configurable", {})

    # Model: experiment override or per-agent deployment config from config.py
    model = (
        configurable.get("model_per_agent", {}).get(agent_name)
        or settings.BEDROCK_MODEL_ROUTING[agent_name]
    )

    # Thinking effort: experiment override → config.py → omit (standard mode)
    effort = (
        configurable.get("thinking_effort_per_agent", {}).get(agent_name)
        or settings.BEDROCK_THINKING_EFFORT.get(agent_name)
    )
    additional_fields = {"thinking": {"type": "adaptive", "effort": effort}} if effort else None

    return ChatBedrockConverse(
        model=model,
        region_name=settings.AWS_DEFAULT_REGION,
        temperature=0,
        max_tokens=MAX_TOKENS[agent_name],
        additional_model_request_fields=additional_fields,
    )


def invoke_structured(llm: ChatBedrockConverse, schema: type[BaseModel], messages: list) -> dict:
    """Invoke LLM with structured output, falling back to raw args on validation error.

    Uses include_raw=True so that when Pydantic rejects the tool call output
    (e.g. wrong Literal category in the wrong slot), we still get the raw args
    dict. A '_parse_error' key is added to the output when this happens.
    """
    structured_llm = llm.with_structured_output(schema, include_raw=True)
    result = structured_llm.invoke(messages)

    if result["parsing_error"]:
        logger.warning("Structured output validation failed for %s: %s",
                       schema.__name__, result["parsing_error"])
        output = result["raw"].tool_calls[0]["args"]
        output["_parse_error"] = str(result["parsing_error"])
        return output

    return result["parsed"].model_dump()
