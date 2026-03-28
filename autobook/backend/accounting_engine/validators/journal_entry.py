def validate_journal_entry(entry: dict) -> dict:
    """Check that a parsed journal entry satisfies accounting rules.

    Checks:
        1. Entry has a non-empty 'lines' list.
        2. Every line has 'account_name', 'type' (debit|credit), and 'amount'.
        3. All amounts > 0.
        4. Sum of debit amounts == sum of credit amounts.

    Args:
        entry: Parsed journal entry dict with at least a 'lines' key.

    Returns:
        {"valid": bool, "errors": list[str]}
    """
    errors: list[str] = []

    lines = entry.get("lines")
    if not lines or not isinstance(lines, list):
        return {"valid": False, "errors": ["Missing or empty 'lines' list"]}

    required_fields = ("account_name", "type", "amount")
    debit_total = 0.0
    credit_total = 0.0

    for i, line in enumerate(lines):
        for field in required_fields:
            if field not in line:
                errors.append(f"Line {i}: missing '{field}'")

        line_type = line.get("type")
        if line_type not in ("debit", "credit"):
            errors.append(f"Line {i}: type must be 'debit' or 'credit', got '{line_type}'")

        amount = line.get("amount")
        if not isinstance(amount, (int, float)):
            errors.append(f"Line {i}: amount must be a number, got {type(amount).__name__}")
            continue

        if amount <= 0:
            errors.append(f"Line {i}: amount must be > 0, got {amount}")

        if line_type == "debit":
            debit_total += amount
        elif line_type == "credit":
            credit_total += amount

    if not errors and abs(debit_total - credit_total) > 0.005:
        errors.append(
            f"Debits ({debit_total:.2f}) != Credits ({credit_total:.2f})"
        )

    return {"valid": len(errors) == 0, "errors": errors}
