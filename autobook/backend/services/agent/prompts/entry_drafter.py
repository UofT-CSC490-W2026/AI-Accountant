"""Prompt builder for Entry Drafter.

Simple composer. Trusts upstream classifications and tax treatment.
Builds the journal entry from classified lines + tax context.
Output: EntryDrafterOutput {reason, lines: [...]}
"""
import json
from services.agent.graph.state import PipelineState
from services.agent.prompts.shared import SHARED_INSTRUCTION
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_user_context,
    build_input_section, to_bedrock_messages,
)
from services.agent.utils.parsers.json_output import DEBIT_SLOTS, CREDIT_SLOTS

# ── Role ─────────────────────────────────────────────────────────────────

_ROLE = """
## Role

Build a complete double-entry journal entry from the given debit/credit \
structure and tax context. Trust the upstream classifications — do not \
re-evaluate them.

You do NOT:
- Re-classify the transaction (classifiers already did that)
- Judge ambiguity (ambiguity detector and decision maker handled that)
- Determine tax treatment (tax specialist handled that)"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the debit and credit structure counts.
2. For each non-zero slot, create that many journal lines. \
Name each account from the business purpose and context of the \
transaction, not from the physical item description. \
Use the most specific account name that is necessary for a correct \
entry — if using a broader name would produce a wrong or misleading \
entry, be specific; otherwise a standard category name is fine.
3. Infer dollar amounts from the transaction text. \
For calculations (PV, interest, allocation), show the formula and \
compute each term. Use actual/365 day-count for interest.
4. If tax specialist says add_tax_lines, add separate tax lines \
using the stated rate and amount.
5. Verify total debits = total credits.
6. If vendor history is available, follow precedent on account selection."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Purchase equipment $20,000 — $5,000 cash, $15,000 loan"
Debit structure: [1,0,0,0,0,0], Credit structure: [1,0,0,1,0,0]
Tax: not applicable
Output: {"reason": "Equipment asset acquired with mixed funding", \
"lines": [{"type": "debit", "account_name": "Equipment", "amount": 20000.00}, \
{"type": "credit", "account_name": "Cash", "amount": 5000.00}, \
{"type": "credit", "account_name": "Loan Payable", "amount": 15000.00}]}
</example>

<example>
Transaction: "Sold products for $5,000 plus 10% tax, cost $3,000"
Debit structure: [1,0,1,0,0,0], Credit structure: [0,0,1,1,0,0]
Tax: add_tax_lines=true, rate=0.10, amount=500
Output: {"reason": "Sale with COGS and tax collected", \
"lines": [{"type": "debit", "account_name": "Cash", "amount": 5500.00}, \
{"type": "debit", "account_name": "Cost of Goods Sold", "amount": 3000.00}, \
{"type": "credit", "account_name": "Sales Revenue", "amount": 5000.00}, \
{"type": "credit", "account_name": "Inventory", "amount": 3000.00}, \
{"type": "credit", "account_name": "Tax Payable", "amount": 500.00}]}
</example>

<example>
Transaction: "Record monthly depreciation on equipment $500"
Debit structure: [0,0,1,0,0,0], Credit structure: [0,0,0,1,0,0]
Tax: not applicable
Output: {"reason": "Depreciation expense with contra-asset", \
"lines": [{"type": "debit", "account_name": "Depreciation Expense", "amount": 500.00}, \
{"type": "credit", "account_name": "Accumulated Depreciation", "amount": 500.00}]}
</example>

<example>
Transaction: "Issued bonds $3,000,000 face, 3-year term, 10% coupon annual, market rate 15%"
Debit structure: [1,0,0,1,0,0], Credit structure: [1,0,0,0,0,0]
Tax: not applicable
Calculation: PV of coupons = sum([300000/1.15**i for i in range(1,4)]) = 685,065
PV of principal = 3000000/1.15**3 = 1,972,545
Total proceeds = 685,065 + 1,972,545 = 2,657,510
Discount = 3,000,000 - 2,657,510 = 342,490
Output: {"reason": "Bonds issued at discount: cash at PV of all future cash flows (coupons + principal)", \
"lines": [{"type": "debit", "account_name": "Cash", "amount": 2657510.00}, \
{"type": "debit", "account_name": "Discount on Bonds Payable", "amount": 342490.00}, \
{"type": "credit", "account_name": "Bonds Payable", "amount": 3000000.00}]}
Note: Bond PV must include BOTH coupon annuity and principal. Omitting coupons is wrong.
</example>"""

# ── Input Format ─────────────────────────────────────────────────────────

_INPUT_FORMAT = """
## Input Format

You will receive these blocks in the user message:

1. <transaction> — The raw transaction description.
2. <context> — The user's business context.
3. <debit_classification> — Classified debit lines with reasons and \
IFRS taxonomy categories.
4. <credit_classification> — Classified credit lines with reasons and \
IFRS taxonomy categories.
5. <tax_context> — Tax treatment from the tax specialist."""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Build the journal entry from the given structure and transaction text. \
Trust the structure counts. Name accounts from business purpose and \
context — be specific when it affects correctness. \
For calculations, show formula and compute each term. \
Add tax lines if indicated. Verify total debits = total credits."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES, _INPUT_FORMAT, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def _extract_classified_lines(state: PipelineState) -> tuple[dict, dict]:
    """Extract classified lines from classifier outputs, with decision maker overrides."""
    debit_out = (state.get("output_debit_classifier") or [None])[-1] or {}
    credit_out = (state.get("output_credit_classifier") or [None])[-1] or {}

    # Extract per-slot classified lines
    debit_lines = {}
    for slot in DEBIT_SLOTS:
        debit_lines[slot] = debit_out.get(slot, [])
    credit_lines = {}
    for slot in CREDIT_SLOTS:
        credit_lines[slot] = credit_out.get(slot, [])

    # Apply decision maker overrides if present
    decision_maker = (state.get("output_decision_maker") or [None])[-1]
    if decision_maker:
        if decision_maker.get("override_debit"):
            # Override replaces all debit lines
            debit_lines = {slot: [] for slot in DEBIT_SLOTS}
            for line in decision_maker["override_debit"]:
                # Place each line in appropriate slot based on category
                # Decision maker provides flat list; keep in asset_increase as default
                debit_lines.setdefault("asset_increase", []).append(line)
        if decision_maker.get("override_credit"):
            credit_lines = {slot: [] for slot in CREDIT_SLOTS}
            for line in decision_maker["override_credit"]:
                credit_lines.setdefault("liability_increase", []).append(line)

    return debit_lines, credit_lines


def build_prompt(state: PipelineState, tax_output: dict | None = None) -> dict:
    """Build the entry drafter prompt with classified lines."""
    if tax_output is None:
        tax_output = (state.get("output_tax_specialist") or [None])[-1]

    debit_lines, credit_lines = _extract_classified_lines(state)

    context = f"<debit_classification>{json.dumps(debit_lines, indent=2)}</debit_classification>\n"
    context += f"<credit_classification>{json.dumps(credit_lines, indent=2)}</credit_classification>\n"
    if tax_output:
        context += f"<tax_context>{json.dumps(tax_output)}</tax_context>\n"

    system_blocks = [
        {"text": SHARED_INSTRUCTION}, CACHE_POINT,
        {"text": AGENT_INSTRUCTION}, CACHE_POINT,
    ]
    transaction = build_transaction(state=state)
    user_ctx = build_user_context(state=state)
    context_block = [{"text": context}]
    task = [{"text": _TASK_REMINDER}]
    message_blocks = transaction + user_ctx + context_block + task

    return to_bedrock_messages(system_blocks, message_blocks)
