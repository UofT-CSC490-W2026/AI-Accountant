"""Prompt builder for Agent 2 — Credit Classifier.

Classifies how many credit-side journal lines fall into each of the 6
directional categories. Output: JSON with tuple and reason.
"""
from services.agent.graph.state import PipelineState
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction,
    build_fix_context, build_rag_examples,
    build_context_section, build_input_section, to_bedrock_messages,
)

# ── 1. Preamble ──────────────────────────────────────────────────────────

_PREAMBLE = """\
You are an accounting classifier in a Canadian automated bookkeeping system. \
All classifications follow IFRS standards."""

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

Every transaction has debit lines and credit lines. Total debits = total \
credits in dollar amounts. Dividends (owner withdrawals) behave like \
expenses: decreased by credit.

Count each economically distinct event as a separate line — if a single \
payment clears an obligation and incurs a new expense, count both. When \
face value and present value differ, count the contra account as its own \
line. Combine into a single line when components share the same account \
and same treatment. Classify by business purpose, not item description. \
Non-depreciable items (land, permanent landscaping) must use distinct \
accounts from depreciable items (improvements, structures)."""

# ── 4. System Knowledge ──────────────────────────────────────────────────

_SYSTEM = """
## System Knowledge

The pipeline represents each journal entry side as a 6-slot tuple (a,b,c,d,e,f). \
Each slot counts the number of lines of that type. Values are LINE COUNTS, \
not dollar amounts.

Credit Tuple:
- a: Liability increase
- b: Equity increase
- c: Revenue increase
- d: Asset decrease
- e: Dividend decrease
- f: Expense decrease"""

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
Transaction: "Receive $1,000 payment from client for services"
Output: {"tuple": [0,0,1,0,0,0], "reason": "Service revenue = revenue increase"}
</example>

<example>
Transaction: "Purchase equipment $20,000 cash plus $30,000 loan"
Output: {"tuple": [1,0,0,1,0,0], "reason": "Cash leaving + loan = asset decrease + liability increase"}
</example>

<example>
Transaction: "Receive refund $300 for returned office supplies"
Output: {"tuple": [0,0,0,0,0,1], "reason": "Supplies expense reversed = expense decrease"}
</example>"""

# ── 7. Input Format ─────────────────────────────────────────────────────

_INPUT_FORMAT = """
## Input Format

You will receive these blocks in the user message:

1. <transaction> — The raw transaction description to classify.
2. <fix_context> (optional) — If present, a previous review rejected this \
classification. Contains guidance on what to fix.
3. <examples> (optional) — Similar past transactions retrieved for reference."""

# ── 8. Task Reminder (appended to end of HumanMessage) ─────────────────

_TASK_REMINDER = """
## Task

Classify the credit side of the given transaction. Apply IFRS standards and \
output the 6-slot credit tuple with a brief reason. Consider any fix context \
or reference examples if provided."""

SYSTEM_INSTRUCTION = "\n".join([
    _PREAMBLE, _ROLE, _DOMAIN, _SYSTEM, _PROCEDURE, _EXAMPLES, _INPUT_FORMAT,
])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the credit classifier prompt with cache breakpoints."""
    # ── § Context (optional reference material) ───────────────────
    fix = build_fix_context(fix_context=fix_context)
    rag = build_rag_examples(rag_examples=rag_examples,
                             label="similar past transactions with correct credit tuples",
                             fields=["transaction", "credit_tuple"])
    context = build_context_section(fix, rag)

    # ── § Input (what to classify) ────────────────────────────────
    transaction = build_transaction(state=state)
    input_section = build_input_section(transaction)

    # ── § Task (last thing before model generates) ────────────────
    task = [{"text": _TASK_REMINDER}]

    # ── Join ──────────────────────────────────────────────────────
    system_blocks = [{"text": SYSTEM_INSTRUCTION}, CACHE_POINT]
    message_blocks = context + input_section + task

    return to_bedrock_messages(system_blocks, message_blocks)
