"""Prompt builder for Credit Classifier.

Classifies credit-side journal lines into 6 directional slots.
Each line gets a reason and an IFRS taxonomy category.
Output: CreditClassifierOutput with list[ClassifiedLine] per slot.
"""
from services.agent.graph.state import PipelineState
from services.agent.prompts.shared import SHARED_INSTRUCTION
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction,
    build_fix_context, build_rag_examples,
    build_context_section, build_input_section, to_bedrock_messages,
)

# ── Role ─────────────────────────────────────────────────────────────────

_ROLE = """
## Role

Given a transaction description, classify the CREDIT side only. For each \
credit-side journal line, identify which directional slot it belongs to and \
assign an IFRS taxonomy category from the list in Domain Knowledge.

Same category = combine into one line. Different category = separate lines.

You do NOT:
- Classify the debit side (separate agent handles that)
- Assign specific account names or dollar amounts (entry drafter does that)
- Check arithmetic balance"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Identify each credit-side journal line implied by the transaction.
3. For each line, determine the directional slot (liability_increase, \
asset_decrease, etc.) and pick the IFRS taxonomy category.
4. If two items share the same category, combine into one line. \
If they have different categories, keep them separate.
5. For each line, state the reason (why it exists) and the category."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Pay monthly rent $2,000"
asset_decrease: [("Cash payment for rent", "Cash and cash equivalents")]
</example>

<example>
Transaction: "Owner invests $50,000 into business"
equity_increase: [("Owner capital contribution", "Issued capital")]
</example>

<example>
Transaction: "Purchase equipment $20,000 cash plus $30,000 loan"
liability_increase: [("New loan for equipment", "Long-term borrowings")]
asset_decrease: [("Cash payment for equipment", "Cash and cash equivalents")]
</example>

<example>
Transaction: "Sell products $5,000 on account, cost $3,000"
revenue_increase: [("Product sale", "Revenue from sale of goods")]
asset_decrease: [("Inventory shipped to customer", "Inventories — merchandise")]
</example>"""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Classify the credit side. For each line, provide the reason and \
IFRS taxonomy category. Same category = combine. Different = separate."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit classifier prompt."""
    fix = build_fix_context(fix_context=fix_context)
    rag = build_rag_examples(rag_examples=rag_examples,
                             label="similar past transactions with correct credit structures",
                             fields=["transaction", "credit_tuple"])
    context = build_context_section(fix, rag)

    transaction = build_transaction(state=state)
    input_section = build_input_section(transaction)

    task = [{"text": _TASK_REMINDER}]

    system_blocks = [
        {"text": SHARED_INSTRUCTION}, CACHE_POINT,
        {"text": AGENT_INSTRUCTION}, CACHE_POINT,
    ]
    message_blocks = context + input_section + task

    return to_bedrock_messages(system_blocks, message_blocks)
