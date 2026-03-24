"""Single agent prompt — classifies AND builds journal entry in one shot.

Best possible single-agent prompt. This is the baseline to beat.
If the pipeline can't outperform this, the decomposition adds no value.
"""
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_fix_context, build_rag_examples,
    to_bedrock_messages,
)
from services.agent.graph.state import PipelineState

_SYSTEM_INSTRUCTION = """\
You are a Canadian bookkeeper. Given a transaction description, produce:
1. A debit 6-tuple classifying debit-side journal lines
2. A credit 6-tuple classifying credit-side journal lines
3. A complete journal entry

## Double-Entry Rules

Total debits = total credits. Account types:
| Type      | Debit Effect | Credit Effect |
|-----------|-------------|--------------|
| Asset     | Increase    | Decrease     |
| Liability | Decrease    | Increase     |
| Equity    | Decrease    | Increase     |
| Revenue   | Decrease    | Increase     |
| Expense   | Increase    | Decrease     |

Dividends behave like expenses: increased by debit.

## Debit Tuple (a,b,c,d,e,f)
Each slot counts debit-side journal lines:
a=Asset↑, b=Dividend↑, c=Expense↑, d=Liability↓, e=Equity↓, f=Revenue↓

## Credit Tuple (a,b,c,d,e,f)
Each slot counts credit-side journal lines:
a=Liability↑, b=Equity↑, c=Revenue↑, d=Asset↓, e=Dividend↓, f=Expense↓

## Journal Entry Schema
{"date": "YYYY-MM-DD", "description": "...", "rationale": "...", \
"lines": [{"account_name": "...", "type": "debit"|"credit", "amount": 0.00}]}

## Examples

<example>
Transaction: "Purchase inventory for $100 cash"
Output: {"debit_tuple": [1,0,0,0,0,0], "credit_tuple": [0,0,0,1,0,0], \
"journal_entry": {"date": "2026-03-24", "description": "Purchase inventory for cash", \
"rationale": "Inventory increases (asset), cash decreases (asset)", \
"lines": [{"account_name": "Inventory", "type": "debit", "amount": 100.00}, \
{"account_name": "Cash", "type": "credit", "amount": 100.00}]}, \
"reason": "Simple asset swap — inventory in, cash out"}
</example>

<example>
Transaction: "Sell inventory (cost $300) for $500 cash"
Output: {"debit_tuple": [1,0,1,0,0,0], "credit_tuple": [0,0,1,1,0,0], \
"journal_entry": {"date": "2026-03-24", "description": "Sale of inventory", \
"rationale": "Cash received at sale price, inventory removed at cost, COGS recognized", \
"lines": [{"account_name": "Cash", "type": "debit", "amount": 500.00}, \
{"account_name": "Cost of Goods Sold", "type": "debit", "amount": 300.00}, \
{"account_name": "Sales Revenue", "type": "credit", "amount": 500.00}, \
{"account_name": "Inventory", "type": "credit", "amount": 300.00}]}, \
"reason": "Compound entry — revenue at sale price, COGS at cost"}
</example>

<example>
Transaction: "Declare $50 dividend"
Output: {"debit_tuple": [0,1,0,0,0,0], "credit_tuple": [1,0,0,0,0,0], \
"journal_entry": {"date": "2026-03-24", "description": "Dividend declaration", \
"rationale": "Retained earnings reduced, dividend payable created", \
"lines": [{"account_name": "Retained Earnings", "type": "debit", "amount": 50.00}, \
{"account_name": "Dividends Payable", "type": "credit", "amount": 50.00}]}, \
"reason": "Dividend increase (slot b), not equity decrease — dividends payable is liability"}
</example>

<example>
Transaction: "Board resolution (no financial impact)"
Output: {"debit_tuple": [0,0,0,0,0,0], "credit_tuple": [0,0,0,0,0,0], \
"journal_entry": null, \
"reason": "No financial impact — no journal entry needed"}
</example>

## Output Format

Return JSON:
{"debit_tuple": [a,b,c,d,e,f], "credit_tuple": [a,b,c,d,e,f], \
"journal_entry": {...} or null, "reason": "brief explanation"}

Verify: total debits = total credits, line count matches tuple sums."""


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> list:
    """Build the single-agent prompt."""
    # ── Build message parts ──────────────────────────────────────────
    transaction = build_transaction(state=state)
    fix         = build_fix_context(fix_context=fix_context)
    rag         = build_rag_examples(rag_examples=rag_examples,
                                    label="similar past transactions for reference",
                                    fields=["transaction", "debit_tuple", "credit_tuple"])

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": _SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = transaction \
                   + [CACHE_POINT] \
                   + fix \
                   + rag

    return to_bedrock_messages(system_blocks, message_blocks)
