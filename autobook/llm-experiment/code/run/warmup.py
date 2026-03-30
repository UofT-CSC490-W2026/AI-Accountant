"""Cache warmup — prime Bedrock prompt caches for V3 agents.

Two cache points per agent:
  1. SHARED_INSTRUCTION (shared across all agents — cached once)
  2. AGENT_INSTRUCTION (per-agent — cached separately)
"""
from __future__ import annotations

from rich.console import Console

console = Console()


def warmup_caches() -> None:
    """Call each V3 agent's LLM once to trigger cache_creation on system prompts.

    First warms the shared instruction (cache point 1), then each agent's
    own instruction (cache point 2). The shared prefix is reused across agents.
    """
    from langchain_core.callbacks import BaseCallbackHandler
    from services.agent.utils.llm import get_llm
    from services.agent.utils.parsers.json_output import _MODELS
    from services.agent.utils.prompt import CACHE_POINT, to_bedrock_messages

    # Shared instruction — same for all agents, cached at point 1
    from services.agent.prompts.shared import SHARED_INSTRUCTION

    # Per-agent instructions — cached at point 2
    from services.agent.prompts.disambiguator import AGENT_INSTRUCTION as AI_AMB
    from services.agent.prompts.complexity_detector import AGENT_INSTRUCTION as AI_COMP
    from services.agent.prompts.debit_classifier import AGENT_INSTRUCTION as AI_DC
    from services.agent.prompts.credit_classifier import AGENT_INSTRUCTION as AI_CC
    from services.agent.prompts.tax_specialist import AGENT_INSTRUCTION as AI_TAX
    from services.agent.prompts.decision_maker import AGENT_INSTRUCTION as AI_DM
    from services.agent.prompts.entry_drafter import AGENT_INSTRUCTION as AI_ED

    agents = [
        ("ambiguity_detector", AI_AMB),
        ("complexity_detector", AI_COMP),
        ("debit_classifier", AI_DC),
        ("credit_classifier", AI_CC),
        ("tax_specialist", AI_TAX),
        ("decision_maker", AI_DM),
        ("entry_drafter", AI_ED),
    ]

    class CacheProbe(BaseCallbackHandler):
        def __init__(self):
            self.usage = {}
        def on_llm_end(self, response, **kwargs):
            if response.generations:
                msg = response.generations[0][0].message
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    self.usage = dict(msg.usage_metadata)

    console.print("[dim]Warming up caches (V3 agents)...[/dim]")
    for agent_name, agent_instruction in agents:
        # Two cache points: shared + agent-specific
        system_blocks = [
            {"text": SHARED_INSTRUCTION}, CACHE_POINT,
            {"text": agent_instruction}, CACHE_POINT,
        ]
        message_blocks = [{"text": "Respond with one word: ready"}]
        messages = to_bedrock_messages(system_blocks, message_blocks)

        pydantic_cls = _MODELS.get(agent_name)
        llm = get_llm(agent_name)
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
