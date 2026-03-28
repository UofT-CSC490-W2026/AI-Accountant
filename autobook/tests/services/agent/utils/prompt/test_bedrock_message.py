from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


# ── Mock langchain_core before importing the module under test ────────────

class _FakeSystemMessage:
    def __init__(self, content):
        self.content = content


class _FakeHumanMessage:
    def __init__(self, content):
        self.content = content


_mock_messages = ModuleType("langchain_core.messages")
_mock_messages.SystemMessage = _FakeSystemMessage
_mock_messages.HumanMessage = _FakeHumanMessage

_mock_lc = ModuleType("langchain_core")
_mock_lc.messages = _mock_messages

sys.modules.setdefault("langchain_core", _mock_lc)
sys.modules.setdefault("langchain_core.messages", _mock_messages)

from services.agent.utils.prompt.bedrock_message import to_bedrock_messages


class TestToBedrockMessages:
    def test_returns_two_messages(self):
        system_blocks = [{"text": "You are an accountant."}]
        message_blocks = [{"text": "Classify this transaction."}]
        result = to_bedrock_messages(system_blocks, message_blocks)
        assert len(result) == 2

    def test_first_is_system_message(self):
        system_blocks = [{"text": "system prompt"}]
        message_blocks = [{"text": "user input"}]
        result = to_bedrock_messages(system_blocks, message_blocks)
        assert type(result[0]).__name__ == "SystemMessage" or type(result[0]).__name__ == "_FakeSystemMessage"
        assert result[0].content == system_blocks

    def test_second_is_human_message(self):
        system_blocks = [{"text": "system prompt"}]
        message_blocks = [{"text": "user input"}]
        result = to_bedrock_messages(system_blocks, message_blocks)
        assert type(result[1]).__name__ == "HumanMessage" or type(result[1]).__name__ == "_FakeHumanMessage"
        assert result[1].content == message_blocks

    def test_empty_blocks(self):
        result = to_bedrock_messages([], [])
        assert len(result) == 2
        assert result[0].content == []
        assert result[1].content == []

    def test_multiple_blocks(self):
        system_blocks = [{"text": "a"}, {"text": "b"}]
        message_blocks = [{"text": "c"}, {"text": "d"}, {"text": "e"}]
        result = to_bedrock_messages(system_blocks, message_blocks)
        assert result[0].content == system_blocks
        assert result[1].content == message_blocks
