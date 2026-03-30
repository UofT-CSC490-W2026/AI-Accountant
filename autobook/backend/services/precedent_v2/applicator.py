"""Step 12: Apply winning label to build a complete journal entry.

Accounts and sides from structure, amounts from ratio × transaction amount,
tax lines recomputed from current rate (never copied from precedent).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from services.precedent_v2.models import Label

# Tax account codes — these lines are always recomputed, never carried from precedent
TAX_ACCOUNT_CODES = {"2100", "2101", "2102"}  # HST/GST Payable, HST/GST Receivable, QST

# Province → tax rate mapping
TAX_RATES = {
    "ON": Decimal("0.13"),   # HST
    "NB": Decimal("0.15"),   # HST
    "NL": Decimal("0.15"),   # HST
    "NS": Decimal("0.15"),   # HST
    "PE": Decimal("0.15"),   # HST
    "BC": Decimal("0.12"),   # GST + PST
    "SK": Decimal("0.11"),   # GST + PST
    "MB": Decimal("0.12"),   # GST + PST
    "AB": Decimal("0.05"),   # GST only
    "NT": Decimal("0.05"),   # GST only
    "NU": Decimal("0.05"),   # GST only
    "YT": Decimal("0.05"),   # GST only
    "QC": Decimal("0.14975"),  # GST + QST
}


def _round_money(value: Decimal) -> float:
    """Round to 2 decimal places for currency."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def apply_label(
    label: Label,
    amount: float,
    province: str = "ON",
) -> dict:
    """Apply the winning label to produce a complete journal entry.

    Args:
        label: The (structure, ratio) label from consensus.
        amount: The new transaction's amount.
        province: Province code for tax recomputation.

    Returns:
        Proposed entry dict with "entry" and "lines" keys.
    """
    tx_amount = Decimal(str(amount))
    lines = []

    # Apply ratio to non-tax lines
    for struct_line, ratio_line in zip(label.structure, label.ratio):
        if struct_line.account_code in TAX_ACCOUNT_CODES:
            continue  # skip tax lines — recomputed below
        line_amount = _round_money(tx_amount * Decimal(str(ratio_line.ratio)))
        lines.append({
            "account_code": struct_line.account_code,
            "type": struct_line.side,
            "amount": line_amount,
            "line_order": len(lines),
        })

    # Recompute tax lines if the original structure had them
    has_tax = any(sl.account_code in TAX_ACCOUNT_CODES for sl in label.structure)
    if has_tax:
        tax_rate = TAX_RATES.get(province, Decimal("0.13"))
        # Find the base amount (sum of debit non-tax lines)
        base = sum(
            Decimal(str(line["amount"]))
            for line in lines
            if line["type"] == "debit"
        )
        tax_amount = _round_money(base * tax_rate)

        # Find the original tax line to determine its side
        for struct_line in label.structure:
            if struct_line.account_code in TAX_ACCOUNT_CODES:
                lines.append({
                    "account_code": struct_line.account_code,
                    "type": struct_line.side,
                    "amount": tax_amount,
                    "line_order": len(lines),
                })

    return {
        "entry": {
            "origin_tier": 1,
            "rationale": f"Precedent bypass (structure_hash={label.structure_hash[:12]})",
        },
        "lines": lines,
    }
