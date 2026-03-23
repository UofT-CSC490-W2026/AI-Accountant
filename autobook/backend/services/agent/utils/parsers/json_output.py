from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ValidationError

from services.agent.graph.state import ENTRY_BUILDER, APPROVER, DIAGNOSTICIAN


# ── Pydantic schemas per agent output ─────────────────────────────────────

class JournalLine(BaseModel):
    account_name: str
    type: Literal["debit", "credit"]
    amount: float


class EntryBuilderOutput(BaseModel):
    date: str
    description: str
    rationale: str | None = None
    lines: list[JournalLine]


class ApproverOutput(BaseModel):
    approved: bool
    confidence: float
    reason: str


class FixPlan(BaseModel):
    agent: int
    error: str
    fix_context: str


class DiagnosticianOutput(BaseModel):
    decision: Literal["FIX", "STUCK"]
    fix_plans: list[FixPlan]


_MODELS: dict[str, type[BaseModel]] = {
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
