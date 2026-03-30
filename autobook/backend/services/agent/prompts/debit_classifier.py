"""Prompt builder for Debit Classifier.

Classifies debit-side journal lines into 6 directional slots.
Each line gets a reason and an IFRS taxonomy category.
Output: DebitClassifierOutput with list[ClassifiedLine] per slot.
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

Given a transaction description, classify the DEBIT side only. For each \
debit-side journal line, identify which directional slot it belongs to and \
assign an IFRS taxonomy category from the list in Domain Knowledge.

Same category = combine into one line. Different category = separate lines.

You do NOT:
- Classify the credit side (separate agent handles that)
- Assign specific account names or dollar amounts (entry drafter does that)
- Check arithmetic balance"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Identify each debit-side journal line implied by the transaction.
3. For each line, determine the directional slot (asset_increase, \
expense_increase, etc.) and pick the IFRS taxonomy category.
4. If two items share the same category, combine into one line. \
If they have different categories, keep them separate.
5. For each line, state the reason (why it exists) and the category."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Pay monthly rent $2,000"
expense_increase: [("Rent payment for the month", "Occupancy expense")]
</example>

<example>
Transaction: "Owner withdraws $5,000 from business"
dividend_increase: [("Owner cash withdrawal", "Dividends declared")]
</example>

<example>
Transaction: "Purchase office desks $2,000 and computers $3,500 cash"
asset_increase: [("Office desks and computers — same PP&E category", "Office equipment")]
Note: desks and computers share the same category, so they combine into 1 line.
</example>

<example>
Transaction: "Purchase land $2M and build fencing $500K"
asset_increase: [("Non-depreciable land", "Land"), ("Depreciable fencing", "Site improvements")]
Note: Land and Site improvements are different categories, so they are 2 lines.
</example>

<example>
Transaction: "Record payroll: production wages $25K, office salaries $20K"
asset_increase: [("Production wages capitalized to WIP", "Inventories — work in progress")]
expense_increase: [("Office salaries", "Employee benefits expense")]
</example>

<example>
Transaction: "Purchased warehouse for $500K, paid with a 5-year note at face value, market rate 8%"
asset_increase: [("Warehouse at present value of note", "Buildings")]
liability_decrease: [("Discount on note payable — contra-liability for difference between face value and PV", "Long-term borrowings")]
Note: When face value and present value differ, the discount is a separate contra-liability line.
</example>"""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Classify the debit side. For each line, provide the reason and \
IFRS taxonomy category. Same category = combine. Different = separate."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the debit classifier prompt with two cache points."""
    fix = build_fix_context(fix_context=fix_context)
    rag = build_rag_examples(rag_examples=rag_examples,
                             label="similar past transactions with correct debit structures",
                             fields=["transaction", "debit_tuple"])
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
