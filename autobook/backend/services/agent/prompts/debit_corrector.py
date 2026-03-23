"""Prompt builder for Agent 3 — Debit Corrector.

Re-evaluates the initial debit tuple using the credit side as cross-validation.
Fixes misclassifications and missing lines. Output: refined 6-tuple.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import build_fix_context, build_rag_examples

_CACHE_POINT = {"cachePoint": {"type": "default"}}

# ── 1. Preamble ──────────────────────────────────────────────────────────

_PREAMBLE = """\
You are an accounting reviewer in a Canadian automated bookkeeping system."""

# ── 2. Role ──────────────────────────────────────────────────────────────

_ROLE = """
## Role

Review and correct a debit tuple produced by a previous classifier. Use the \
credit tuple as cross-validation context.

You do NOT:
- Perform arithmetic balance checks (Agent 5's job)
- Assign account titles or names (Agent 5's job)
- Assign dollar amounts (Agent 5's job)
- Match debit line count to credit line count (they are independent)
- Correct the credit tuple (separate agent handles that)"""

# ── 3. Domain Knowledge ──────────────────────────────────────────────────

_DOMAIN = """
## Domain Knowledge

Account types and their debit behavior:
| Account Type | Debit Effect |
|-------------|-------------|
| Asset       | Increase    |
| Dividend    | Increase    |
| Expense     | Increase    |
| Liability   | Decrease    |
| Equity      | Decrease    |
| Revenue     | Decrease    |

Common misclassifications:
- COGS as asset increase instead of expense increase
- Owner withdrawals as expense instead of dividend increase
- Loan payments as expense instead of liability decrease"""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM = """
## System Knowledge

Debit Tuple (a, b, c, d, e, f):
| Slot | Category            |
|------|---------------------|
| a    | Asset increase      |
| b    | Dividend increase   |
| c    | Expense increase    |
| d    | Liability decrease  |
| e    | Equity decrease     |
| f    | Revenue decrease    |

IMPORTANT: The cross-validation tuple (credit side) may itself contain errors. \
It was produced by a separate classifier that can also make mistakes. Use it as \
a signal, not as ground truth. Prioritize transaction semantics over tuple \
consistency."""

# ── 5. Procedure ─────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description.
2. Read the initial debit tuple and the credit tuple.
3. Check each debit slot against the transaction semantics.
4. Use the credit tuple as a cross-validation signal:
   - If credit shows "asset decrease" (inventory leaving), debit should likely
     have "expense increase" (COGS), not "asset increase."
5. Correct any misclassifications or missing lines.
6. If the initial tuple is already correct, return it unchanged."""

# ── 6. Examples ──────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Sell inventory (cost $100k) for $150k cash"
Initial debit tuple: (2,0,0,0,0,0)
Credit tuple: (0,0,1,1,0,0)
Reasoning: Credit has asset decrease (inventory leaving) — debit COGS should be expense increase, not second asset increase.
Output: (1,0,1,0,0,0)
</example>

<example>
Transaction: "Pay off accounts payable $5,000"
Initial debit tuple: (0,0,1,0,0,0)
Credit tuple: (0,0,0,1,0,0)
Reasoning: Paying AP is liability decrease, not expense increase.
Output: (0,0,0,1,0,0)
</example>

<example>
Transaction: "Owner withdraws $3,000"
Initial debit tuple: (0,0,1,0,0,0)
Credit tuple: (0,0,0,1,0,0)
Reasoning: Owner withdrawal is dividend increase (slot b), not expense.
Output: (0,1,0,0,0,0)
</example>

<example>
Transaction: "Pay monthly rent $2,000"
Initial debit tuple: (0,0,1,0,0,0)
Credit tuple: (0,0,0,1,0,0)
Reasoning: Correct. Rent is expense increase.
Output: (0,0,1,0,0,0)
</example>

<example>
Transaction: "Pay employee wages $3,000 and remit source deductions $800"
Initial debit tuple: (0,0,1,0,0,0)
Credit tuple: (0,0,0,1,0,0)
Reasoning: Two separate debit lines — wages expense AND source deductions expense. Initial missed one.
Output: (0,0,2,0,0,0)
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
    """Build the debit corrector prompt with cache breakpoints."""
    system = [{"text": SYSTEM_INSTRUCTION}, _CACHE_POINT]

    text = state.get("enriched_text") or state["transaction_text"]
    transaction_block = f"<transaction>{text}</transaction>"

    dynamic_block = (
        f"<initial_debit_tuple>{state.get('initial_debit_tuple', '')}</initial_debit_tuple>\n"
        f"<credit_tuple>{state.get('initial_credit_tuple', '')}</credit_tuple>"
    )

    content = [{"text": transaction_block}, _CACHE_POINT, {"text": dynamic_block}]

    content += build_fix_context(fix_context=fix_context)
    content += build_rag_examples(
        rag_examples=rag_examples,
        label="similar past corrections for reference",
        fields=["transaction", "before", "after"],
    )

    return {
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }
