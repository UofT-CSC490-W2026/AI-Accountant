"""Prompt builder for Agent 2 — Credit Classifier.

Classifies how many credit-side journal lines fall into each of the 6
directional categories. Output: JSON with tuple and reason.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_fix_context, build_rag_examples,
    to_bedrock_messages,
)

# ── 1. Preamble ──────────────────────────────────────────────────────────

_PREAMBLE = """\
You are an accounting classifier in a Canadian automated bookkeeping system."""

# ── 2. Role ──────────────────────────────────────────────────────────────

_ROLE = """
## Role

Given a transaction description, classify the CREDIT side only. Count how many \
credit-side journal lines fall into each of the 6 directional categories.

You do NOT:
- Classify the debit side (separate agent handles that)
- Assign account names or dollar amounts
- Check arithmetic balance"""

# ── 3. Domain Knowledge ──────────────────────────────────────────────────

_DOMAIN = """
## Domain Knowledge

Every transaction has debit lines and credit lines. Total debits = total credits \
in dollar amounts.

Account types and their credit behavior:
| Account Type | Credit Effect |
|-------------|--------------|
| Liability   | Increase     |
| Equity      | Increase     |
| Revenue     | Increase     |
| Asset       | Decrease     |
| Dividend    | Decrease     |
| Expense     | Decrease     |

Dividends (owner withdrawals) behave like expenses: decreased by credit."""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM = """
## System Knowledge

Credit Tuple (a, b, c, d, e, f) — each slot counts credit-side journal lines:

| Slot | Category             | Meaning                         |
|------|---------------------|---------------------------------|
| a    | Liability increase   | Taking on new obligations       |
| b    | Equity increase      | Increasing owner's equity       |
| c    | Revenue increase     | Earning income                  |
| d    | Asset decrease       | Giving up or consuming assets   |
| e    | Dividend decrease    | Reversing owner withdrawals     |
| f    | Expense decrease     | Reversing or reducing expenses  |

Each value is a LINE COUNT, not a dollar amount."""

# ── 5. Procedure ─────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Identify each credit-side journal line implied by the transaction.
3. For each credit line, determine which directional category it falls into.
4. Count the lines per category and output the 6-tuple."""

# ── 6. Examples ──────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Sell inventory (cost $100k) for $150k cash"
Output: {"tuple": [0,0,1,1,0,0], "reason": "Revenue increase (sales) + asset decrease (inventory leaving)"}
</example>

<example>
Transaction: "Pay monthly rent $2,000"
Output: {"tuple": [0,0,0,1,0,0], "reason": "Cash leaving = asset decrease"}
</example>

<example>
Transaction: "Owner invests $50,000 into business"
Output: {"tuple": [0,1,0,0,0,0], "reason": "Owner capital = equity increase"}
</example>

<example>
Transaction: "Take out $25,000 bank loan"
Output: {"tuple": [1,0,0,0,0,0], "reason": "Loan = liability increase"}
</example>

<example>
Transaction: "Purchase equipment $20,000 cash plus $30,000 loan"
Output: {"tuple": [1,0,0,1,0,0], "reason": "Cash leaving + loan = asset decrease + liability increase"}
</example>

<example>
Transaction: "Receive refund $300 for returned office supplies"
Output: {"tuple": [0,0,0,0,0,1], "reason": "Supplies expense reversed = expense decrease"}
</example>"""

# ── 7. Output Format ─────────────────────────────────────────────────────

_OUTPUT_FORMAT = """
## Output Format

Return JSON: {"tuple": [a,b,c,d,e,f], "reason": "brief explanation"}
Each tuple value must be a non-negative integer."""

SYSTEM_INSTRUCTION = "\n".join([
    _PREAMBLE, _ROLE, _DOMAIN, _SYSTEM, _PROCEDURE, _EXAMPLES, _OUTPUT_FORMAT,
])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit classifier prompt with cache breakpoints."""
    # ── Build message parts ──────────────────────────────────────────
    transaction = build_transaction(state=state)
    fix         = build_fix_context(fix_context=fix_context)
    rag         = build_rag_examples(rag_examples=rag_examples,
                                    label="similar past transactions with correct credit tuples",
                                    fields=["transaction", "credit_tuple"])

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = transaction \
                   + [CACHE_POINT] \
                   + fix \
                   + rag

    return to_bedrock_messages(system_blocks, message_blocks)
