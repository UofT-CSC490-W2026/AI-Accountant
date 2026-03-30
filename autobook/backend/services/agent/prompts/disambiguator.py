"""Prompt builder for Ambiguity Detector (legacy name: Disambiguator).

Analyzes transaction for ambiguity. Resolves what it can, flags what it can't.
Output: AmbiguityDetectorOutput {ambiguities: [...]}
"""
from services.agent.graph.state import PipelineState
from services.agent.prompts.shared import SHARED_INSTRUCTION
from services.agent.utils.prompt import (
    CACHE_POINT, build_transaction, build_user_context,
    build_fix_context, build_rag_examples,
    build_context_section, build_input_section, to_bedrock_messages,
)

# ── Role ─────────────────────────────────────────────────────────────────

_ROLE = """
## Role

You analyze transaction descriptions to identify factual ambiguities that \
would prevent a correct journal entry from being created. You resolve what \
you can, and flag only what survives all resolution attempts.

You may reason about whether different interpretations would produce \
different journal entries — this is needed to assess ambiguities. \
But you do NOT build or output entries.

You run in parallel with other agents (classifiers, complexity detector, \
tax specialist). If you flag unresolved ambiguities, a decision maker \
downstream will review your analysis and decide whether to proceed or \
request clarification.

Do not flag accounting treatment that has one correct answer under IFRS. \
However, if the correct treatment depends on a business decision not stated \
in the transaction (management's intent, entity's policy election, risk \
transfer assessment), that is a factual ambiguity — flag it."""

# ── Procedure ────────────────────────────────────────────────────────────

_PROCEDURE = """
## Procedure

1. Read the transaction description and user context.

2. List every potential ambiguity and the question that would resolve it.

3. Among the ambiguities above, discard any where answering the question \
would NOT change which accounts are debited/credited, or the amounts.

4. Among the remaining, resolve any where the answer is already stated \
or clearly implied in the transaction text.

5. Among the remaining, resolve any where standard accounting convention \
or the conventional terms provide a clear default interpretation.

6. Among the remaining, resolve any using the user context (business type, \
ownership structure, province, or vendor history).

7. For each ambiguity from step 2, output resolved or unresolved with \
the appropriate fields.

8. Clarification questions must be:
   - Answerable by the person who initiated the transaction
   - About business facts (purpose, intent, context), not accounting treatment

Only flag ambiguities that arise from what the transaction text actually \
says. Do not invent ambiguities about information the transaction does \
not mention."""

# ── Examples ─────────────────────────────────────────────────────────────

_EXAMPLES = """
## Examples

<example>
Input: "Paid $200 to Tim" + (restaurant, sole proprietor, ON)
Output: {"ambiguities": [{"aspect": "purpose of payment to Tim", "resolved": true, \
"resolution": "Restaurant context — likely contractor payment for restaurant services"}]}
</example>

<example>
Input: "Acme Corp paid $350 for flowers using the corporate credit card."
Output: {"ambiguities": [{"aspect": "purpose of flower purchase", "resolved": false, \
"options": ["Office decoration", "Client gift", "Employee recognition", "Event decoration"], \
"clarification_question": "What was the business purpose of this flower purchase?", \
"why_entry_depends_on_clarification": "Each purpose maps to a different expense account", \
"why_ambiguity_not_resolved_by_given_info": "No convention for flower purchases, business type does not narrow it"}]}
</example>

<example>
Input: "Purchased office furniture for $1,200 on account" + (general, corporation, ON)
Output: {"ambiguities": []}
</example>

<example>
Input: "Settled outstanding invoice of $450" + (general, corporation, ON)
Output: {"ambiguities": []}
Note: "Which vendor?" discarded — vendor identity doesn't change the entry.
</example>

<example>
Input: "Company acquired machinery and paid $50,000 for a 3-year extended warranty."
Output: {"ambiguities": [{"aspect": "warranty accounting treatment", "resolved": false, \
"options": ["Capitalize as part of asset cost", "Expense as service contract"], \
"clarification_question": "Is the extended warranty a separately identifiable service contract?", \
"why_entry_depends_on_clarification": "Capitalized increases asset; expensed is immediate period cost", \
"why_ambiguity_not_resolved_by_given_info": "Treatment depends on entity assessment, not determinable from text"}]}
</example>"""

# ── Task Reminder ────────────────────────────────────────────────────────

_TASK_REMINDER = """
## Task

Analyze the transaction for factual ambiguities. Apply the procedure: \
list, discard, resolve, and flag only what survives. \
If nothing is ambiguous, return an empty ambiguities list."""

AGENT_INSTRUCTION = "\n".join([_ROLE, _PROCEDURE, _EXAMPLES, ])

# Legacy — for warmup compatibility
SYSTEM_INSTRUCTION = "\n".join([SHARED_INSTRUCTION, AGENT_INSTRUCTION])


def build_prompt(state: PipelineState, rag_examples: list[dict],
                 fix_context: str | None = None) -> dict:
    """Build the ambiguity detector prompt."""
    fix = build_fix_context(fix_context=fix_context)
    rag = build_rag_examples(rag_examples=rag_examples,
                             label="similar past disambiguations for reference",
                             fields=["input", "output"])
    context = build_context_section(fix, rag)

    transaction = build_transaction(state=state)
    user_ctx = build_user_context(state=state)
    input_section = build_input_section(transaction, user_ctx)

    task = [{"text": _TASK_REMINDER}]

    system_blocks = [
        {"text": SHARED_INSTRUCTION}, CACHE_POINT,
        {"text": AGENT_INSTRUCTION}, CACHE_POINT,
    ]
    message_blocks = context + input_section + task

    return to_bedrock_messages(system_blocks, message_blocks)
