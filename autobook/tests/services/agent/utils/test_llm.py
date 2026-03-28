"""Tests for services/agent/utils/llm.py — get_llm().

langchain_aws and langchain_core are not in dev deps, so we stub them
in sys.modules before importing the module under test.
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub langchain_aws and langchain_core.runnables before import
# ---------------------------------------------------------------------------

_mock_lc_aws = ModuleType("langchain_aws")
_mock_lc_aws.ChatBedrockConverse = MagicMock()

_mock_lc_core = ModuleType("langchain_core")
_mock_lc_runnables = ModuleType("langchain_core.runnables")
_mock_lc_runnables.RunnableConfig = dict
_mock_lc_core.runnables = _mock_lc_runnables

# Also stub langchain_core.messages in case other imports pull it in
_mock_lc_messages = ModuleType("langchain_core.messages")
_mock_lc_messages.SystemMessage = MagicMock
_mock_lc_messages.HumanMessage = MagicMock
_mock_lc_core.messages = _mock_lc_messages

sys.modules.setdefault("langchain_aws", _mock_lc_aws)
sys.modules.setdefault("langchain_core", _mock_lc_core)
sys.modules.setdefault("langchain_core.runnables", _mock_lc_runnables)
sys.modules.setdefault("langchain_core.messages", _mock_lc_messages)

from services.agent.utils.llm import MAX_TOKENS, get_llm  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_default_config(mock_get_settings, mock_chat_cls):
    """get_llm with no config returns ChatBedrockConverse with settings defaults."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "ca-central-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "debit_classifier": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {}
    mock_get_settings.return_value = mock_settings

    result = get_llm("debit_classifier")

    mock_chat_cls.assert_called_once_with(
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        region_name="ca-central-1",
        temperature=0,
        max_tokens=2000,
        additional_model_request_fields=None,
    )
    assert result is mock_chat_cls.return_value


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_with_thinking_effort(mock_get_settings, mock_chat_cls):
    """get_llm passes thinking effort from settings when present."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "us-east-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "approver": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {"approver": "high"}
    mock_get_settings.return_value = mock_settings

    get_llm("approver")

    call_kwargs = mock_chat_cls.call_args.kwargs
    assert call_kwargs["additional_model_request_fields"] == {
        "thinking": {"type": "adaptive", "effort": "high"}
    }


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_config_override_model(mock_get_settings, mock_chat_cls):
    """Config override replaces the model from settings."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "ca-central-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "entry_builder": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {}
    mock_get_settings.return_value = mock_settings

    config = {
        "configurable": {
            "model_per_agent": {"entry_builder": "us.anthropic.claude-3-haiku-v1:0"},
        }
    }
    get_llm("entry_builder", config=config)

    call_kwargs = mock_chat_cls.call_args.kwargs
    assert call_kwargs["model"] == "us.anthropic.claude-3-haiku-v1:0"


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_config_override_thinking_effort(mock_get_settings, mock_chat_cls):
    """Config override for thinking effort takes precedence over settings."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "ca-central-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "disambiguator": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {"disambiguator": "low"}
    mock_get_settings.return_value = mock_settings

    config = {
        "configurable": {
            "thinking_effort_per_agent": {"disambiguator": "medium"},
        }
    }
    get_llm("disambiguator", config=config)

    call_kwargs = mock_chat_cls.call_args.kwargs
    assert call_kwargs["additional_model_request_fields"] == {
        "thinking": {"type": "adaptive", "effort": "medium"}
    }


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_max_tokens_per_agent(mock_get_settings, mock_chat_cls):
    """Each agent name maps to the correct max_tokens value."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "ca-central-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "diagnostician": "some-model",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {}
    mock_get_settings.return_value = mock_settings

    get_llm("diagnostician")

    call_kwargs = mock_chat_cls.call_args.kwargs
    assert call_kwargs["max_tokens"] == MAX_TOKENS["diagnostician"]
    assert call_kwargs["max_tokens"] == 2000


@patch("services.agent.utils.llm.ChatBedrockConverse")
@patch("services.agent.utils.llm.get_settings")
def test_get_llm_no_thinking_effort_passes_none(mock_get_settings, mock_chat_cls):
    """When no thinking effort set anywhere, additional_model_request_fields is None."""
    mock_settings = MagicMock()
    mock_settings.AWS_DEFAULT_REGION = "ca-central-1"
    mock_settings.BEDROCK_MODEL_ROUTING = {
        "credit_classifier": "some-model",
    }
    mock_settings.BEDROCK_THINKING_EFFORT = {}
    mock_get_settings.return_value = mock_settings

    get_llm("credit_classifier", config=None)

    call_kwargs = mock_chat_cls.call_args.kwargs
    assert call_kwargs["additional_model_request_fields"] is None
