"""Prompt builder for Decision Maker.

Reviews all upstream outputs. Can override classifications.
Only runs when ambiguity or complexity is flagged.
Output: DecisionMakerOutput {decision: proceed|missing_info|llm_stuck, ...}
"""
import json
from services.agent.graph.state import PipelineState
from services.agent.prompts.shared import SHARED_INSTRUCTION
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_user_context,
    build_input_section, to_bedrock_messages,
)

# ── Role ─────────────────────────────────────────────────────────────────

_ROLE = """
## Role

You are called because upstream agents flagged potential issues. \
Review all upstream outputs and make a final decision:

- proceed: the entry can be built despite the flags
- missing_info: the transaction is missing business facts needed \
for a correct entry. The same transaction could produce structurally \
different entries depending on unknown facts.
- llm_stuck: the system lacks the knowledge to handle this correctly. \
A human expert is needed.

You may override debit/credit classifications, but only when you \
have a strong reason that the overridden version is more correct. \
If the classifier provides specific reasoning (e.g., distinguishing \
depreciable from non-depreciable items), do not override unless you \
can show that reasoning is factually wrong."""

# ── Agent-Specific Knowledge ─────────────────────────────────────────────

_AGENT_KNOWLEDGE = """
## Decision Criteria

When to decide missing_info:
- The account name or amount would differ depending on an unknown \
business fact (not just the debit/credit structure — even if the \
tuple is the same, different account names count as different entries)
- The fact is not determinable from the transaction text, \
accounting conventions, or user context
- The person who initiated the transaction could answer the question

When to decide llm_stuck:
- The transaction requires specialized calculations the system \
cannot reliably perform
- The accounting standard requires entity-specific information \
not available in the transaction text

When to proceed:
- The flags are overly cautious — the entry can be built with \
reasonable defaults
- The ambiguity does not change the account name, amount, or structure
- The complexity is within standard IFRS knowledge"""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Review each unresolved ambiguity from the ambiguity detector. \
For each, apply this test:
   - Would the account name or amount differ depending on the answer? \
(Even if the debit/credit tuple stays the same, different account names \
means the ambiguity is material.)
   - AND: Is the answer NOT determinable from the transaction text, \
accounting conventions, or user context?
   If BOTH true, this is genuinely missing information. \
If either is false, the ambiguity detector was overly cautious — proceed.

2. Review each skeptical flag from the complexity detector. \
For each: is the system truly unable to handle this?

3. Review the debit and credit classifications. \
For each classified line: is the reason valid and the category correct? \
If a line's category is wrong, or lines should be combined/split, \
override with corrected classified lines.

4. Synthesize all assessments into a final decision."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Ambiguity: "purpose of flower purchase" — unresolved, 4 options
Assessment: Each option maps to a different expense account. Entry structure differs.
Decision: missing_info
Questions: ["What was the business purpose of this flower purchase?"]
</example>

<example>
Complexity: "convertible bond with warrants" — skeptical
Assessment: Requires compound instrument split. System cannot reliably compute.
Decision: llm_stuck
Stuck reason: "Compound instrument split requires market rate estimation not available"
</example>

<example>
Ambiguity: "sale vs collateralized borrowing" — unresolved
Transaction: "Company received $500,000 from a bank, pledging receivables"
Assessment: Sale removes receivables, borrowing keeps them — structurally different entries. \
Not determinable from text. Both tests pass.
Decision: missing_info
Questions: ["Was this a sale of receivables or a secured borrowing?"]
</example>

<example>
Ambiguity: "capitalization vs expense for advertising" — unresolved
Assessment: Standard IAS 38.69 — advertising is always expensed. \
Account name does not differ (always expense). Disambiguator was overly cautious.
Decision: proceed
</example>

<example>
Ambiguity: "purpose of meal expense" — unresolved, 5 options
Assessment: Different purposes map to different account names \
(meeting expense vs entertainment vs employee benefits). \
The tuple is the same (debit expense, credit liability) but the \
account name differs materially. Not determinable from text.
Decision: missing_info
Questions: ["What was the business purpose of this meal?"]
</example>"""

# ── Input Format ─────────────────────────────────────────────────────────

_INPUT_FORMAT = """
## Input Format

You will receive these blocks in the user message:

1. <transaction> — The raw transaction description.
2. <context> — The user's business context.
3. <ambiguity_detector> — Upstream ambiguity analysis.
4. <complexity_detector> — Upstream complexity assessment.
5. <debit_classifier> — Upstream debit classification.
6. <credit_classifier> — Upstream credit classification.
7. <tax_specialist> — Upstream tax treatment."""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Review all upstream outputs. For each flagged issue, assess whether \
it changes the account name or amount (not just the tuple). \
Override classifications only with strong factual reason. \
Set the final decision."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _AGENT_KNOWLEDGE, _PROCEDURE, _EXAMPLES, _INPUT_FORMAT, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState) -> dict:
    """Build the decision maker prompt with all upstream outputs."""
    ambiguity = (state.get("output_ambiguity_detector") or [None])[-1]
    complexity = (state.get("output_complexity_detector") or [None])[-1]
    debit = (state.get("output_debit_classifier") or [None])[-1]
    credit = (state.get("output_credit_classifier") or [None])[-1]
    tax = (state.get("output_tax_specialist") or [None])[-1]

    upstream = ""
    if ambiguity:
        upstream += f"<ambiguity_detector>\n{json.dumps(ambiguity, indent=2)}\n</ambiguity_detector>\n\n"
    if complexity:
        upstream += f"<complexity_detector>\n{json.dumps(complexity, indent=2)}\n</complexity_detector>\n\n"
    if debit:
        upstream += f"<debit_classifier>\n{json.dumps(debit, indent=2)}\n</debit_classifier>\n\n"
    if credit:
        upstream += f"<credit_classifier>\n{json.dumps(credit, indent=2)}\n</credit_classifier>\n\n"
    if tax:
        upstream += f"<tax_specialist>\n{json.dumps(tax, indent=2)}\n</tax_specialist>\n\n"

    system_blocks = [
        {"text": SHARED_INSTRUCTION}, CACHE_POINT,
        {"text": AGENT_INSTRUCTION}, CACHE_POINT,
    ]
    transaction = build_transaction(state=state)
    user_ctx = build_user_context(state=state)
    upstream_block = [{"text": upstream}] if upstream else []
    task = [{"text": _TASK_REMINDER}]
    message_blocks = transaction + user_ctx + upstream_block + task

    return to_bedrock_messages(system_blocks, message_blocks)
