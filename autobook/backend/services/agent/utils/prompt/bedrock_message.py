"""Convert prompt blocks to LangChain message objects for ChatBedrockConverse.

Isolates Bedrock-specific message format. If provider changes, only this
file needs updating.
"""
from langchain_core.messages import HumanMessage, SystemMessage


def to_bedrock_messages(system_blocks: list[dict],
                        message_blocks: list[dict]) -> list:
    """Convert raw content blocks to LangChain message objects.

    Args:
        system_blocks: System prompt content blocks (text + cachePoints).
        message_blocks: User message content blocks (text + cachePoints).

    Returns:
        List of [SystemMessage, HumanMessage] for ChatBedrockConverse.invoke().
    """
    return [
        SystemMessage(content=system_blocks),
        HumanMessage(content=message_blocks),
    ]
