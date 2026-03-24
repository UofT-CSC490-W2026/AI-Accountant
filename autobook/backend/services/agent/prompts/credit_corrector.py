"""Prompt builder for Agent 4 — Credit Corrector.

Re-evaluates the initial credit tuple using the debit side as cross-validation.
Fixes misclassifications and missing lines. Output: JSON with tuple and reason.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_tuples, build_fix_context, build_rag_examples,
    to_bedrock_messages,
)

# ── 1. Preamble ──────────────────────────────────────────────────────────

_PREAMBLE = """\
You are an accounting reviewer in a Canadian automated bookkeeping system."""

# ── 2. Role ──────────────────────────────────────────────────────────────

_ROLE = """
## Role

Review and correct a credit tuple produced by a previous classifier. Use the \
debit tuple as cross-validation context.

You do NOT:
- Perform arithmetic balance checks (Agent 5's job)
- Assign account titles or names (Agent 5's job)
- Assign dollar amounts (Agent 5's job)
- Match credit line count to debit line count (they are independent)
- Correct the debit tuple (separate agent handles that)"""

# ── 3. Domain Knowledge ──────────────────────────────────────────────────

_DOMAIN = """
## Domain Knowledge

Account types and their credit behavior:
| Account Type | Credit Effect |
|-------------|--------------|
| Liability   | Increase     |
| Equity      | Increase     |
| Revenue     | Increase     |
| Asset       | Decrease     |
| Dividend    | Decrease     |
| Expense     | Decrease     |

Common misclassifications:
- Owner's Capital as liability increase instead of equity increase
- Missing inventory credit (asset decrease) on sales with COGS
- Loan proceeds as revenue instead of liability increase"""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM = """
## System Knowledge

Credit Tuple (a, b, c, d, e, f):
| Slot | Category             |
|------|----------------------|
| a    | Liability increase   |
| b    | Equity increase      |
| c    | Revenue increase     |
| d    | Asset decrease       |
| e    | Dividend decrease    |
| f    | Expense decrease     |

IMPORTANT: The cross-validation tuple (debit side) may itself contain errors. \
It was produced by a separate classifier that can also make mistakes. Use it as \
a signal, not as ground truth. Prioritize transaction semantics over tuple \
consistency."""

# ── 5. Procedure ─────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Read the initial credit tuple and the debit tuple.
3. Check each credit slot against the transaction semantics.
4. Use the debit tuple as a cross-validation signal:
   - If debit shows "expense increase" (COGS), credit should likely
     have "asset decrease" (inventory leaving).
5. Correct any misclassifications or missing lines.
6. If the initial tuple is already correct, return it unchanged."""

# ── 6. Examples ──────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Owner invests $50,000 into business"
Initial credit tuple: (1,0,0,0,0,0), Debit tuple: (1,0,0,0,0,0)
Output: {"tuple": [0,1,0,0,0,0], "reason": "Owner investment is equity increase, not liability"}
</example>

<example>
Transaction: "Sell inventory (cost $100k) for $150k cash"
Initial credit tuple: (0,0,1,0,0,0), Debit tuple: (1,0,1,0,0,0)
Output: {"tuple": [0,0,1,1,0,0], "reason": "Debit has COGS — inventory must leave, add asset decrease"}
</example>

<example>
Transaction: "Receive $1,000 payment from client"
Initial credit tuple: (0,0,1,0,0,0), Debit tuple: (1,0,0,0,0,0)
Output: {"tuple": [0,0,1,0,0,0], "reason": "No correction needed, revenue increase is correct"}
</example>

<example>
Transaction: "Take out $25,000 bank loan"
Initial credit tuple: (0,0,1,0,0,0), Debit tuple: (1,0,0,0,0,0)
Output: {"tuple": [1,0,0,0,0,0], "reason": "Loan proceeds are liability increase, not revenue"}
</example>"""

# ── 7. Output Format ─────────────────────────────────────────────────────

_OUTPUT_FORMAT = """
## Output Format

Return JSON: {"tuple": [a,b,c,d,e,f], "reason": "brief explanation of correction or why no change"}
If the initial tuple is already correct, return it unchanged with reason."""

SYSTEM_INSTRUCTION = "\n".join([
    _PREAMBLE, _ROLE, _DOMAIN, _SYSTEM, _PROCEDURE, _EXAMPLES,
])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit corrector prompt with cache breakpoints."""
    # ── Build message parts ──────────────────────────────────────────
    i           = state["iteration"]
    transaction = build_transaction(state=state)
    initial     = build_tuples(debit=state["output_debit_classifier"][i]["tuple"], credit=state["output_credit_classifier"][i]["tuple"])
    fix         = build_fix_context(fix_context=fix_context)
    rag         = build_rag_examples(rag_examples=rag_examples,
                                    label="similar past corrections for reference",
                                    fields=["transaction", "before", "after"])

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = transaction \
                   + [CACHE_POINT] \
                   + initial \
                   + fix \
                   + rag

    return to_bedrock_messages(system_blocks, message_blocks)
