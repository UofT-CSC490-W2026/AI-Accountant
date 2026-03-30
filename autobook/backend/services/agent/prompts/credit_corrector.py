"""Prompt builder for Agent 4 — Credit Corrector.

Re-evaluates the initial credit tuple using the debit side as cross-validation.
Only corrects when the initial credit is clearly wrong based on transaction
semantics. Output: JSON with tuple and reason.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_labeled_tuples,
    build_fix_context, build_rag_examples,
    build_context_section, build_input_section, to_bedrock_messages,
)

# ── 1. Preamble ──────────────────────────────────────────────────────────

_PREAMBLE = """\
You are an accounting reviewer in an automated bookkeeping system. \
All classifications follow IFRS standards."""

# ── 2. Role ──────────────────────────────────────────────────────────────

_ROLE = """
## Role

Review a credit tuple produced by a previous classifier. Use the debit tuple \
as cross-validation context.

You are an objective refiner. You have no bias toward changing or keeping the \
initial tuple. Change it only when it is clearly wrong based on the \
transaction's accounting semantics.

You do NOT:
- Perform arithmetic balance checks (Agent 5's job)
- Assign account titles or names (Agent 5's job)
- Assign dollar amounts (Agent 5's job)
- Match credit line count to debit line count (they are independent)
- Correct the debit tuple (separate agent handles that)
- Change the credit tuple just because it "looks inconsistent" with the debit"""

# ── 3. Domain Knowledge ──────────────────────────────────────────────────

_DOMAIN = """
## Domain Knowledge (IFRS)

Debiting an account means:
- Asset: increases its balance
- Dividend: increases its balance
- Expense: increases its balance
- Liability: decreases its balance
- Equity: decreases its balance
- Revenue: decreases its balance

Crediting an account means:
- Liability: increases its balance
- Equity: increases its balance
- Revenue: increases its balance
- Asset: decreases its balance
- Dividend: decreases its balance
- Expense: decreases its balance

Common misclassifications to watch for:
- Owner's capital recorded as liability increase instead of equity increase
- Missing inventory credit (asset decrease) on sales with COGS
- Loan proceeds recorded as revenue instead of liability increase
- Bundled payments counted as one event type when they contain \
distinct economic events (e.g., liability clearing + new expense)
- Contra accounts collapsed into a net amount instead of recorded \
separately (e.g., discount on bonds omitted, net PV used instead)
- Items classified by description instead of business purpose
- Components with same account/treatment not combined into single line
- Non-depreciable items (land) mixed with depreciable items (improvements)"""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM_KNOWLEDGE = """
## System Knowledge

The pipeline represents each journal entry side as a 6-slot tuple (a,b,c,d,e,f). \
Each slot counts the number of lines of that type.

Credit Tuple:
- a: Liability increase
- b: Equity increase
- c: Revenue increase
- d: Asset decrease
- e: Dividend decrease
- f: Expense decrease

Debit Tuple (for cross-validation only):
- a: Asset increase
- b: Dividend increase
- c: Expense increase
- d: Liability decrease
- e: Equity decrease
- f: Revenue decrease

IMPORTANT: The debit tuple may itself contain errors — it was produced by a \
separate classifier. Use it as a sanity-check signal, not as ground truth."""

# ── 5. Procedure ─────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read and understand the transaction.
2. Glance at the initial credit tuple and the debit tuple.
3. Check for tension between them:
   - If they agree (the debit and credit sides tell a consistent story), \
that is a good sign. Sanity-check the initial credit against the transaction \
semantics and return it.
   - If there is tension (the two sides seem to contradict), think about why. \
Determine whether the credit is actually wrong, or the debit is the one with \
the error. Remember: the debit may be wrong too.
4. Only change the credit tuple if it is clearly wrong based on what the \
transaction actually is. Do not change it merely because it looks inconsistent \
with the debit."""

# ── 6. Examples ──────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Transaction: "Owner invests $50,000 into business"
Initial credit: (1,0,0,0,0,0), Debit: (1,0,0,0,0,0)
Output: {"tuple": [0,1,0,0,0,0], "reason": "Owner investment is equity increase, not liability increase."}
</example>

<example>
Transaction: "Receive $1,000 payment from client for services"
Initial credit: (0,0,1,0,0,0), Debit: (1,0,0,0,0,0)
Output: {"tuple": [0,0,1,0,0,0], "reason": "Service revenue is a revenue increase. No correction needed."}
</example>

<example>
Transaction: "Take out $25,000 bank loan"
Initial credit: (0,0,1,0,0,0), Debit: (1,0,0,0,0,0)
Output: {"tuple": [1,0,0,0,0,0], "reason": "Loan proceeds are a liability increase, not revenue."}
</example>

<example>
Transaction: "Record monthly amortization of prepaid rent $500"
Initial credit: (0,0,0,1,0,0), Debit: (0,0,1,0,0,0)
Output: {"tuple": [0,0,0,1,0,0], "reason": "Prepaid rent decreasing is an asset decrease. No correction needed."}
</example>

<example>
Transaction: "Customer pays $2,000 deposit for future services"
Initial credit: (0,0,1,0,0,0), Debit: (1,0,0,0,0,0)
Output: {"tuple": [1,0,0,0,0,0], "reason": "Unearned revenue from a deposit is a liability increase, not revenue. Revenue is recognized when services are delivered."}
</example>"""

# ── 7. Input Format ─────────────────────────────────────────────────────

_INPUT_FORMAT = """
## Input Format

You will receive these blocks in the user message:

1. <transaction> — The raw transaction description to review.
2. <initial_credit_tuple> — The credit classification from the previous agent. \
This is what you are reviewing. Includes inline slot labels.
3. <debit_tuple> — The debit classification from a separate agent. \
For cross-validation only. May contain its own errors.
4. <fix_context> (optional) — If present, a previous review rejected this \
classification. Contains guidance on what to fix.
5. <examples> (optional) — Similar past transactions retrieved for reference."""

# ── 8. Task Reminder (appended to end of HumanMessage) ─────────────────

_TASK_REMINDER = """
## Task

Review the initial credit tuple against the debit tuple for the given \
transaction. Apply IFRS standards, follow the procedure above, and consider \
any fix context or reference examples if provided. Return the credit tuple \
corrected or unchanged."""

SYSTEM_INSTRUCTION = "\n".join([
    _PREAMBLE, _ROLE, _DOMAIN, _SYSTEM_KNOWLEDGE, _PROCEDURE, _EXAMPLES,
    _INPUT_FORMAT,
])


def _build_labeled_credit_tuples(debit, credit) -> list[dict]:
    """Build tuple block with credit as primary, debit as cross-validation."""
    return [{"text": (
        "Initial credit classification from the previous classifier:\n"
        "<initial_credit_tuple>\n"
        f"  {credit}\n"
        "  Slots: a=liability increase, b=equity increase, c=revenue increase, "
        "d=asset decrease, e=dividend decrease, f=expense decrease\n"
        "</initial_credit_tuple>\n\n"
        "Debit classification from a separate classifier (for cross-validation only):\n"
        "<debit_tuple>\n"
        f"  {debit}\n"
        "  Slots: a=asset increase, b=dividend increase, c=expense increase, "
        "d=liability decrease, e=equity decrease, f=revenue decrease\n"
        "</debit_tuple>"
    )}]


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit corrector prompt with cache breakpoints."""
    i = state["iteration"]

    # ── § Context (optional reference material) ───────────────────
    fix = build_fix_context(fix_context=fix_context)
    rag = build_rag_examples(rag_examples=rag_examples,
                             label="similar past corrections for reference",
                             fields=["transaction", "before", "after"])
    context = build_context_section(fix, rag)

    # ── § Input (what to review) ──────────────────────────────────
    transaction = build_transaction(state=state)
    tuples = _build_labeled_credit_tuples(
        debit=state["output_debit_classifier"][i]["tuple"],
        credit=state["output_credit_classifier"][i]["tuple"],
    )
    input_section = build_input_section(transaction, tuples)

    # ── § Task (last thing before model generates) ────────────────
    task = [{"text": _TASK_REMINDER}]

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = context + input_section + task

    return to_bedrock_messages(system_blocks, message_blocks)
