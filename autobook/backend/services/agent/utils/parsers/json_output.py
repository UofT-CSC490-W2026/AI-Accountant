from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from services.agent.graph.state import (
    DISAMBIGUATOR, DEBIT_CLASSIFIER, CREDIT_CLASSIFIER,
    DEBIT_CORRECTOR, CREDIT_CORRECTOR, ENTRY_BUILDER,
    APPROVER, DIAGNOSTICIAN,
)


# ── Pydantic schemas per agent output ─────────────────────────────────────

class DisambiguatorOutput(BaseModel):
    enriched_text: str
    reason: str = Field(description="What was ambiguous and how context resolved it")


class DebitClassifierOutput(BaseModel):
    tuple: tuple[int, int, int, int, int, int]
    reason: str = Field(description="For each debit line, what account type it falls under and why")


class CreditClassifierOutput(BaseModel):
    tuple: tuple[int, int, int, int, int, int]
    reason: str = Field(description="For each credit line, what account type it falls under and why")


class DebitCorrectorOutput(BaseModel):
    tuple: tuple[int, int, int, int, int, int]
    reason: str = Field(description="What was wrong with the initial tuple and how you fixed it, or why it was already correct")


class CreditCorrectorOutput(BaseModel):
    tuple: tuple[int, int, int, int, int, int]
    reason: str = Field(description="What was wrong with the initial tuple and how you fixed it, or why it was already correct")


class JournalLine(BaseModel):
    account_name: str
    type: Literal["debit", "credit"]
    amount: float


class EntryBuilderOutput(BaseModel):
    date: str
    description: str
    rationale: str = Field(description="Why these accounts were chosen and how amounts were determined")
    lines: list[JournalLine]


class ApproverOutput(BaseModel):
    approved: bool
    confidence: float
    reason: str = Field(description="What specific checks passed or which specific issue was found")


class FixPlan(BaseModel):
    agent: int = Field(description="Agent index 0-5")
    error: str = Field(description="What the agent got wrong")
    fix_context: str = Field(description="Guidance for the agent on how to fix it")


class DiagnosticianOutput(BaseModel):
    decision: Literal["FIX", "STUCK"]
    fix_plans: list[FixPlan]
    reason: str = Field(description="Which agent made the mistake, what it was, and why it is the root cause")
    reason: str


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
        agent_name: One of "entry_builder", "approver", "diagnostician".
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
