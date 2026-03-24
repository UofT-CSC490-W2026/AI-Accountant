"""Accounting engine tools — database queries called by agent nodes.

These are stubs returning placeholder data. Other team members implement
the real versions against PostgreSQL. Agent nodes import from here.
"""


def vendor_history_lookup(user_id: str, vendor_name: str) -> list[dict]:
    """Find how this vendor was handled before for this user.

    Args:
        user_id: The user's UUID.
        vendor_name: Vendor/counterparty name (e.g. "Kheela's Hardware").

    Returns:
        List of past journal entries for this vendor, each with:
        - account_name: str
        - account_code: str
        - type: "debit" | "credit"
        - amount: float
        - description: str
        Empty list if no history found.

    Called by: Agent 0 (Disambiguator), Agent 5 (Entry Builder).
    """
    return []


def coa_lookup(user_id: str, account_type: str | None = None) -> list[dict]:
    """Return the user's available chart of accounts.

    Args:
        user_id: The user's UUID.
        account_type: Optional filter — "asset", "liability", "equity",
                      "revenue", "expense". None returns all accounts.

    Returns:
        List of accounts, each with:
        - account_code: str
        - account_name: str
        - account_type: str ("asset" | "liability" | "equity" | "revenue" | "expense")

    Called by: Agent 5 (Entry Builder).
    """
    return []


def tax_rules_lookup(province: str, transaction_type: str) -> dict:
    """Return applicable tax rate and rules for the given context.

    Args:
        province: Canadian province code (e.g. "ON", "BC", "AB").
        transaction_type: Classification of the transaction
                          (e.g. "purchase", "sale", "payroll").

    Returns:
        Dict with:
        - rate: float (e.g. 0.13 for 13% HST)
        - taxable: bool (whether this transaction type is taxable)

    Called by: Agent 5 (Entry Builder).
    """
    return {}
