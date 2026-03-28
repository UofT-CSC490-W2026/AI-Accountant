"""Validation node — sits between Agent 5 (Entry Builder) and Agent 6 (Approver).

Pure Python logic, no LLM. Validates journal entry business rules.
Stores errors in state instead of raising — preserves all pipeline progress.
Graph routing checks validation_error to decide whether to continue or END.
"""
from services.agent.graph.state import PipelineState
from accounting_engine.validators import validate_journal_entry, validate_tax


def validation_node(state: PipelineState) -> dict:
    """Validate journal entry and tax rules. Stores errors in state."""
    i = state["iteration"]
    entry = state["output_entry_builder"][i]

    # No-entry case (e.g. "Board resolution") — skip validation
    if entry is None or not entry.get("lines"):
        return {"validation_error": None}
    # All-zero amounts = LLM produced placeholder lines with no real entry
    if all(line.get("amount", 0) == 0 for line in entry.get("lines", [])):
        return {"validation_error": None}

    errors = []

    validation = validate_journal_entry(entry)
    if not validation["valid"]:
        errors.extend(validation["errors"])

    user_ctx = state.get("user_context", {})
    tax_validation = validate_tax(
        entry,
        province=user_ctx.get("province", "ON"),
        tax_rate=0.13,
    )
    if not tax_validation["valid"]:
        errors.extend(tax_validation["errors"])

    return {"validation_error": errors if errors else None}
