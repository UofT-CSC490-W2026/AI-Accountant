"""Validation node — sits between Agent 5 (Entry Builder) and Agent 6 (Approver).

Pure Python logic, no LLM. Validates journal entry business rules.
Raises ValueError on failure — RetryPolicy retries entry_builder.
"""
from services.agent.graph.state import PipelineState
from accounting_engine.validators import validate_journal_entry, validate_tax


def validation_node(state: PipelineState) -> dict:
    """Validate journal entry and tax rules."""
    i = state["iteration"]
    entry = state["output_entry_builder"][i]

    # No-entry case (e.g. "Board resolution") — skip validation
    if entry is None or not entry.get("lines"):
        return {}

    validation = validate_journal_entry(entry)
    if not validation["valid"]:
        raise ValueError(f"Journal entry validation failed: {validation['errors']}")

    user_ctx = state.get("user_context", {})
    tax_validation = validate_tax(
        entry,
        province=user_ctx.get("province", "ON"),
        tax_rate=0.13,
    )
    if not tax_validation["valid"]:
        raise ValueError(f"Tax validation failed: {tax_validation['errors']}")

    return {}
