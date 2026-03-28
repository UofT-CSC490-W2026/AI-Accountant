"""Cache warmup — prime Bedrock prompt caches for all agents."""
from __future__ import annotations

from rich.console import Console

console = Console()


def warmup_caches() -> None:
    """Call each agent's LLM once to trigger cache_creation on system prompts."""
    from langchain_core.callbacks import BaseCallbackHandler
    from services.agent.utils.llm import get_llm
    from services.agent.utils.parsers.json_output import _MODELS
    from services.agent.prompts.disambiguator import SYSTEM_INSTRUCTION as P0
    from services.agent.prompts.debit_classifier import SYSTEM_INSTRUCTION as P1
    from services.agent.prompts.credit_classifier import SYSTEM_INSTRUCTION as P2
    from services.agent.prompts.debit_corrector import SYSTEM_INSTRUCTION as P3
    from services.agent.prompts.credit_corrector import SYSTEM_INSTRUCTION as P4
    from services.agent.prompts.entry_builder import _build_system_instruction
    P5 = _build_system_instruction({})
    from services.agent.prompts.approver import SYSTEM_INSTRUCTION as P6
    from services.agent.prompts.diagnostician import SYSTEM_INSTRUCTION as P7
    from variants.single_agent.prompt import _SYSTEM_INSTRUCTION as P_SINGLE
    from variants.single_agent.graph import SingleAgentOutput
    from services.agent.utils.prompt import CACHE_POINT, to_bedrock_messages

    prompts = [
        ("disambiguator", P0), ("debit_classifier", P1),
        ("credit_classifier", P2), ("debit_corrector", P3),
        ("credit_corrector", P4), ("entry_builder", P5),
        ("approver", P6), ("diagnostician", P7),
        ("single_agent", P_SINGLE),
    ]

    class CacheProbe(BaseCallbackHandler):
        def __init__(self):
            self.usage = {}
        def on_llm_end(self, response, **kwargs):
            if response.generations:
                msg = response.generations[0][0].message
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    self.usage = dict(msg.usage_metadata)

    console.print("[dim]Warming up caches...[/dim]")
    for agent_name, system_text in prompts:
        system_blocks = [{"text": system_text}, CACHE_POINT]
        message_blocks = [{"text": "Respond with one word: ready"}]
        messages = to_bedrock_messages(system_blocks, message_blocks)

        pydantic_cls = SingleAgentOutput if agent_name == "single_agent" else _MODELS[agent_name]
        llm = get_llm("entry_builder" if agent_name == "single_agent" else agent_name)
        structured = llm.with_structured_output(pydantic_cls)

        probe = CacheProbe()
        try:
            structured.invoke(messages, config={"callbacks": [probe]})
        except Exception:
            pass

        details = probe.usage.get("input_token_details", {})
        cw = details.get("cache_creation", 0)
        cr = details.get("cache_read", 0)
        if cw > 0:
            status = f"cache_creation={cw}"
        elif cr > 0:
            status = f"cache_read={cr} (already warm)"
        else:
            status = "not cached (below threshold)"
        console.print(f"  {agent_name:25s} {status}")

    console.print("[dim]Warmup complete.[/dim]\n")
