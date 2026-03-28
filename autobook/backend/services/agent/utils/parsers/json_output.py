from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from services.agent.graph.state import (
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    APPROVER, DIAGNOSTICIAN,
)


# ── Pydantic schemas per agent output ─────────────────────────────────────

class Ambiguity(BaseModel):
    aspect: str = Field(description="What is ambiguous")
    resolved: bool
    resolution: str | None = Field(default=None, description="How it was resolved, if resolved")
    options: list[str] | None = Field(default=None, description="Possible interpretations, if unresolved")
    clarification_question: str | None = Field(default=None, description="Question for the person who initiated the transaction, if unresolved")
    why_entry_differs: str | None = Field(default=None, description="How the entry changes depending on the answer, if unresolved")
    why_not_resolved: str | None = Field(default=None, description="Why the text, conventions, and context don't resolve it, if unresolved")


class DisambiguatorOutput(BaseModel):
    ambiguities: list[Ambiguity] = Field(description="List of identified ambiguities in the transaction")


class DebitClassifierOutput(BaseModel):
    reason: str = Field(description="For each debit line, what account type it falls under and why")
    tuple: tuple[int, int, int, int, int, int]


class CreditClassifierOutput(BaseModel):
    reason: str = Field(description="For each credit line, what account type it falls under and why")
    tuple: tuple[int, int, int, int, int, int]


class DebitCorrectorOutput(BaseModel):
    reason: str = Field(description="What was wrong with the initial tuple and how you fixed it, or why it was already correct")
    tuple: tuple[int, int, int, int, int, int]


class CreditCorrectorOutput(BaseModel):
    reason: str = Field(description="What was wrong with the initial tuple and how you fixed it, or why it was already correct")
    tuple: tuple[int, int, int, int, int, int]


class JournalLine(BaseModel):
    account_name: str
    type: Literal["debit", "credit"]
    amount: float


class AmbiguityResponse(BaseModel):
    aspect: str = Field(description="The ambiguity aspect from the disambiguator")
    action: Literal["proceed", "incomplete"] = Field(
        description="proceed = ambiguity does not affect entry; incomplete = need clarification",
    )
    reason: str = Field(description="Why this ambiguity does or does not affect the entry")


class EntryBuilderOutput(BaseModel):
    date: str
    description: str
    rationale: str = Field(description="Why these accounts were chosen and how amounts were determined")
    lines: list[JournalLine]
    disambiguator_responses: list[AmbiguityResponse] | None = Field(
        default=None,
        description="Required when disambiguator opinions contain unresolved ambiguities. One response per unresolved ambiguity.",
    )
    decision: Literal["APPROVED", "INCOMPLETE_INFORMATION", "STUCK"] | None = Field(
        default=None,
        description="Pipeline decision. Set only when this agent is the terminal decision-maker (no approver).",
    )
    clarification_questions: list[str] | None = Field(
        default=None,
        description="Questions that, once answered, allow the correct entry to be built. Only for INCOMPLETE_INFORMATION.",
    )
    stuck_reason: str | None = Field(
        default=None,
        description="Concise explanation of why the entry cannot be determined. Only for STUCK.",
    )


class ApproverOutput(BaseModel):
    reason: str = Field(description="What specific checks passed or which specific issue was found")
    decision: Literal["APPROVED", "REJECTED", "STUCK"]
    confidence: Literal["VERY_CONFIDENT", "SOMEWHAT_CONFIDENT", "SOMEWHAT_UNCERTAIN", "VERY_UNCERTAIN"]


class FixPlan(BaseModel):
    agent: int = Field(description="Agent index 0-5")
    fix_context: str = Field(description="One sentence: what to fix and how")


class DiagnosticianOutput(BaseModel):
    reasoning: str = Field(description="Trace the error to its root cause agent and explain why")
    decision: Literal["FIX", "STUCK"]
    fix_plans: list[FixPlan]
    stuck_reason: str | None = Field(
        default=None,
        description="Concise explanation for the user/expert of why this cannot be resolved. Only for STUCK.",
    )


_MODELS: dict[str, type[BaseModel]] = {
    DISAMBIGUATOR: DisambiguatorOutput,
    DEBIT_CLASSIFIER: DebitClassifierOutput,
    CREDIT_CLASSIFIER: CreditClassifierOutput,
    DEBIT_CORRECTOR: DebitCorrectorOutput,
    CREDIT_CORRECTOR: CreditCorrectorOutput,
    ENTRY_BUILDER: EntryBuilderOutput,
    APPROVER: ApproverOutput,
    DIAGNOSTICIAN: DiagnosticianOutput,
}


# ── Parser ────────────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    """Remove markdown code fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return cleaned


def parse_json_output(agent_name: str, raw: str) -> dict | None:
    """Parse an LLM JSON output string and validate against agent schema.

    Args:
        agent_name: One of the 8 agent names.
        raw: Raw LLM output string (expected to be JSON).

    Returns:
        Parsed dict if valid, None if parsing or schema check fails.
    """
    model = _MODELS.get(agent_name)
    if model is None:
        return None

    try:
        cleaned = _strip_fences(raw)
        result = model.model_validate_json(cleaned)
        return result.model_dump()
    except (ValidationError, ValueError):
        return None
