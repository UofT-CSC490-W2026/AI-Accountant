"""Prompt builder for Agent 4 — Credit Corrector.

Re-evaluates the initial credit tuple using the debit side as cross-validation.
Fixes misclassifications and missing lines. Output: refined 6-tuple.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import append_fix_context, append_rag_examples

_CACHE_POINT = {"cachePoint": {"type": "default"}}

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
Initial credit tuple: (1,0,0,0,0,0)
Debit tuple: (1,0,0,0,0,0)
Reasoning: Debit is asset increase (cash). Owner investment is equity increase, not liability.
Output: (0,1,0,0,0,0)
</example>

<example>
Transaction: "Sell inventory (cost $100k) for $150k cash"
Initial credit tuple: (0,0,1,0,0,0)
Debit tuple: (1,0,1,0,0,0)
Reasoning: Debit has COGS (expense increase) — inventory must leave. Missing asset decrease.
Output: (0,0,1,1,0,0)
</example>

<example>
Transaction: "Receive $1,000 payment from client"
Initial credit tuple: (0,0,1,0,0,0)
Debit tuple: (1,0,0,0,0,0)
Reasoning: Correct. Revenue increase for service payment.
Output: (0,0,1,0,0,0)
</example>

<example>
Transaction: "Take out $25,000 bank loan"
Initial credit tuple: (0,0,1,0,0,0)
Debit tuple: (1,0,0,0,0,0)
Reasoning: Loan proceeds are liability increase, not revenue.
Output: (1,0,0,0,0,0)
</example>

<example>
Transaction: "Pay employee wages $3,000 and remit $800 to CRA"
Initial credit tuple: (0,0,0,1,0,0)
Debit tuple: (0,0,2,0,0,0)
Reasoning: Debit has 2 expense lines. Credit should have asset decrease (cash for wages) plus liability decrease (remittance clears payable). Two credit lines.
Output: (0,0,0,1,0,0)
</example>"""

# ── 7. Output Format ─────────────────────────────────────────────────────

_OUTPUT_FORMAT = """
## Output Format

Return ONLY the corrected 6-tuple as (a,b,c,d,e,f). If the initial tuple \
is already correct, return it unchanged. No explanation."""

SYSTEM_INSTRUCTION = "\n".join([
    _PREAMBLE, _ROLE, _DOMAIN, _SYSTEM, _PROCEDURE, _EXAMPLES, _OUTPUT_FORMAT,
])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit corrector prompt with cache breakpoints."""
    system = [{"text": SYSTEM_INSTRUCTION}, _CACHE_POINT]

    text = state.get("enriched_text") or state["transaction_text"]
    transaction_block = f"<transaction>{text}</transaction>"

    dynamic_block = (
        f"<debit_tuple>{state.get('initial_debit_tuple', '')}</debit_tuple>\n"
        f"<initial_credit_tuple>{state.get('initial_credit_tuple', '')}</initial_credit_tuple>"
    )

    content = [{"text": transaction_block}, _CACHE_POINT, {"text": dynamic_block}]

    append_fix_context(content, fix_context)
    append_rag_examples(content, rag_examples,
                        "similar past corrections for reference",
                        ["transaction", "before", "after"])

    return {
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }
