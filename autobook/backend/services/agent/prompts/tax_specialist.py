"""Prompt builder for Tax Specialist.

Determines tax treatment from transaction text.
Output: TaxSpecialistOutput {reasoning, tax_mentioned, taxable, ...}
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

Determine the tax treatment for this transaction. Your output tells the \
entry drafter whether to add tax lines and how to record them.

You do NOT:
- Build the journal entry (entry drafter handles that)
- Classify debit/credit lines (classifiers handle that)
- Assess ambiguity (ambiguity detector handles that)"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction text. Does it explicitly mention tax?
   - "plus 10% tax", "$6,900 tax", "inclusive of sales tax" → tax_mentioned = true
   - No mention of tax at all → tax_mentioned = false

2. Is this transaction type taxable? (Refer to tax categories in Domain Knowledge)

3. Should tax lines be added?
   - If tax_mentioned = true → add_tax_lines = true, use stated rate/amount
   - If tax_mentioned = false → add_tax_lines = false, regardless of taxability
   - Never infer tax when the transaction text does not mention it

4. How to record?
   - Purchases: recoverable → Tax Receivable (asset)
   - Purchases: non-recoverable → part of expense amount
   - Sales: collected → Tax Payable (liability)"""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Purchased supplies for $500 plus 10% tax"
Output: {"reasoning": "Text states 10% tax on $500 purchase", \
"tax_mentioned": true, "taxable": true, "add_tax_lines": true, \
"tax_rate": 0.10, "tax_amount": 50.0, "treatment": "recoverable"}
</example>

<example>
Transaction: "Paid employee salaries of $3,000 in cash"
Output: {"reasoning": "Payroll is not a taxable supply", \
"tax_mentioned": false, "taxable": false, "add_tax_lines": false, \
"tax_rate": null, "tax_amount": null, "treatment": "not_applicable"}
</example>

<example>
Transaction: "Paid monthly rent $2,000 (no tax mentioned)"
Output: {"reasoning": "Rent is taxable but text does not mention tax", \
"tax_mentioned": false, "taxable": true, "add_tax_lines": false, \
"tax_rate": null, "tax_amount": null, "treatment": "not_applicable"}
</example>

<example>
Transaction: "Sold products for $5,000 plus 13% tax"
Output: {"reasoning": "Sale with 13% tax collected", \
"tax_mentioned": true, "taxable": true, "add_tax_lines": true, \
"tax_rate": 0.13, "tax_amount": 650.0, "treatment": "recoverable"}
</example>"""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Determine the tax treatment for this transaction. \
If tax is mentioned, extract the rate and amount. \
If not mentioned, do not add tax lines."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState, rag_examples: list[dict] | None = None) -> dict:
    """Build the tax specialist prompt."""
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
