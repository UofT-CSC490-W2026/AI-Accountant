"""Prompt builder for Agent 1 — Debit Classifier.

Classifies how many debit-side journal lines fall into each of the 6
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

Given a transaction description, classify the DEBIT side only. Count how many \
debit-side journal lines fall into each of the 6 directional categories.

You do NOT:
- Classify the credit side (separate agent handles that)
- Assign account names or dollar amounts
- Check arithmetic balance"""

# ── 3. Domain Knowledge ──────────────────────────────────────────────────

_DOMAIN = """
## Domain Knowledge

Every transaction has debit lines and credit lines. Total debits = total credits \
in dollar amounts.

Account types and their debit behavior:
| Account Type | Debit Effect |
|-------------|-------------|
| Asset       | Increase    |
| Dividend    | Increase    |
| Expense     | Increase    |
| Liability   | Decrease    |
| Equity      | Decrease    |
| Revenue     | Decrease    |

Dividends (owner withdrawals) behave like expenses: increased by debit."""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM = """
## System Knowledge

Debit Tuple (a, b, c, d, e, f) — each slot counts debit-side journal lines:

| Slot | Category            | Meaning                        |
|------|--------------------|---------------------------------|
| a    | Asset increase      | Acquiring or receiving assets   |
| b    | Dividend increase   | Owner withdrawals               |
| c    | Expense increase    | Consuming resources or services |
| d    | Liability decrease  | Paying off obligations          |
| e    | Equity decrease     | Reducing owner's equity         |
| f    | Revenue decrease    | Reversing or reducing revenue   |

Each value is a LINE COUNT, not a dollar amount."""

# ── 5. Procedure ─────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Identify each debit-side journal line implied by the transaction.
3. For each debit line, determine which directional category it falls into.
4. Count the lines per category and output the 6-tuple."""

# ── 6. Examples ──────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Sell inventory (cost $100k) for $150k cash"
Output: {"tuple": [1,0,1,0,0,0], "reason": "Cash received = asset increase, COGS = expense increase"}
</example>

<example>
Transaction: "Pay monthly rent $2,000"
Output: {"tuple": [0,0,1,0,0,0], "reason": "Rent = expense increase"}
</example>

<example>
Transaction: "Owner withdraws $5,000 from business"
Output: {"tuple": [0,1,0,0,0,0], "reason": "Owner draw = dividend increase, NOT expense"}
</example>

<example>
Transaction: "Pay off $10,000 bank loan"
Output: {"tuple": [0,0,0,1,0,0], "reason": "Loan payoff = liability decrease"}
</example>

<example>
Transaction: "Purchase equipment $20,000 cash plus $30,000 loan"
Output: {"tuple": [1,0,0,0,0,0], "reason": "Equipment = 1 asset increase despite two funding sources"}
</example>

<example>
Transaction: "Issue refund $500 to customer and write off $100 bad debt"
Output: {"tuple": [0,0,1,0,0,1], "reason": "Refund = revenue decrease, bad debt = expense increase"}
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
    """Build the debit classifier prompt with cache breakpoints."""
    # ── Build message parts ──────────────────────────────────────────
    transaction = build_transaction(state=state)
    fix         = build_fix_context(fix_context=fix_context)
    rag         = build_rag_examples(rag_examples=rag_examples,
                                    label="similar past transactions with correct debit tuples",
                                    fields=["transaction", "debit_tuple"])

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = transaction \
                   + [CACHE_POINT] \
                   + fix \
                   + rag

    return to_bedrock_messages(system_blocks, message_blocks)
