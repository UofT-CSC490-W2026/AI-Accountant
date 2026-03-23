from typing import Any

from langchain_aws import ChatBedrockConverse

from config import get_settings

# Model IDs — us. prefix required for ca-central-1 cross-region inference
_SONNET = "us.anthropic.claude-sonnet-4-6-20251001-v1:0"
_HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_OPUS = "us.anthropic.claude-opus-4-6-20251001-v1:0"

# Default: Sonnet for all agents
DEFAULT_MODEL_ROUTING: dict[str, str] = {
    "disambiguator":    _SONNET,
    "debit_classifier": _SONNET,
    "credit_classifier": _SONNET,
    "debit_corrector":  _SONNET,
    "credit_corrector": _SONNET,
    "entry_builder":    _SONNET,
    "approver":         _SONNET,
    "diagnostician":    _SONNET,
}

# Per-agent max output tokens (from agent-pipeline.md Constrained Output table)
MAX_TOKENS: dict[str, int] = {
    "disambiguator":    50,
    "debit_classifier": 10,
    "credit_classifier": 10,
    "debit_corrector":  10,
    "credit_corrector": 10,
    "entry_builder":    200,
    "approver":         50,
    "diagnostician":    100,
}


def get_llm(
    agent_name: str,
    ablation: dict[str, Any] | None = None,
) -> ChatBedrockConverse:
    """Return a configured ChatBedrockConverse client for the given agent.

    Args:
        agent_name: One of the 8 agent names (e.g. "debit_classifier").
        ablation: Optional ablation config — overrides model and thinking effort.

    Returns:
        Configured ChatBedrockConverse instance.
    """
    settings = get_settings()

    # Model ID: ablation override or default routing
    if ablation and ablation.get("model_per_agent", {}).get(agent_name):
        model_id = ablation["model_per_agent"][agent_name]
    else:
        model_id = DEFAULT_MODEL_ROUTING[agent_name]

    max_tokens = MAX_TOKENS[agent_name]

    # Adaptive thinking effort: set via ablation, omitted for standard mode
    additional_fields: dict = {}
    if ablation:
        effort = ablation.get("thinking_effort_per_agent", {}).get(agent_name)
        if effort:
            additional_fields["thinking"] = {"type": "adaptive", "effort": effort}

    return ChatBedrockConverse(
        model=model_id,
        region_name=settings.AWS_DEFAULT_REGION,
        max_tokens=max_tokens,
        additional_model_request_fields=additional_fields if additional_fields else None,
    )
