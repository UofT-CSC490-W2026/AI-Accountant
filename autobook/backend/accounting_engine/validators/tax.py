def validate_tax(entry: dict, province: str, tax_rate: float) -> dict:
    """Check that tax lines in a journal entry have correct math.

    Stub — real implementation by other team members.

    Checks (when implemented):
        1. If tax lines present: rate x base amount == tax line amount.
        2. If tax lines absent on a taxable transaction: flag as warning.

    Does NOT generate tax lines — Agent 5 generates them. This only
    validates the math.

    Args:
        entry: Parsed journal entry dict.
        province: Canadian province code (e.g. "ON").
        tax_rate: Expected tax rate (e.g. 0.13 for HST).

    Returns:
        {"valid": bool, "errors": list[str]}
    """
    return {"valid": True, "errors": []}
