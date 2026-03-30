"""Prompt builder for Complexity Detector.

Flags transactions that exceed LLM capability or knowledge.
Output: ComplexityDetectorOutput {flags: [...]}
"""
from services.agent.graph.state import PipelineState
from services.agent.prompts.shared import SHARED_INSTRUCTION
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_user_context,
    build_input_section, to_bedrock_messages,
)

# ── Role ─────────────────────────────────────────────────────────────────

_ROLE = """
## Role

Assess whether this transaction can be correctly handled by an automated \
system using standard IFRS knowledge. Flag aspects where the system \
lacks the domain knowledge or capability to produce a correct entry.

This is NOT about missing business facts (the ambiguity detector handles \
that). This is about whether the accounting treatment itself is beyond \
what the system can reliably compute.

You do NOT:
- Build entries
- Classify debit/credit lines
- Assess ambiguity from missing facts"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Identify each aspect of the transaction.
3. For each aspect, assess: can the system handle this correctly \
with standard IFRS knowledge?
4. If skeptical, state what knowledge gap exists and what the best \
attempt would produce.

Most transactions are straightforward — only flag genuine knowledge gaps."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Purchased inventory for $500 cash"
Output: {"flags": [{"aspect": "inventory purchase", "skeptical": false}]}
</example>

<example>
Transaction: "Issued convertible bonds with detachable warrants for $10M"
Output: {"flags": [{"aspect": "convertible bond with warrants", \
"why_llm_cannot_do_this": "Requires splitting compound instrument into \
liability and equity components using residual method with market rate estimation", \
"what_is_best_llm_can_do": "Record at face value without component split", \
"skeptical": true}]}
</example>

<example>
Transaction: "Paid monthly rent $2,000"
Output: {"flags": [{"aspect": "rent payment", "skeptical": false}]}
</example>"""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Assess the complexity of this transaction. Flag any aspects that \
are beyond the system's reliable capability."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState, rag_examples: list[dict] | None = None) -> dict:
    """Build the complexity detector prompt."""
    system_blocks = [
        {"text": SHARED_INSTRUCTION}, CACHE_POINT,
        {"text": AGENT_INSTRUCTION}, CACHE_POINT,
    ]
    transaction = build_transaction(state=state)
    user_ctx = build_user_context(state=state)
    input_section = build_input_section(transaction, user_ctx)
    task = [{"text": _TASK_REMINDER}]
    message_blocks = input_section + task

    return to_bedrock_messages(system_blocks, message_blocks)
