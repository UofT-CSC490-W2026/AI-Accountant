from __future__ import annotations

from dataclasses import dataclass
from datetime import date


UNKNOWN_DESTINATION_ACCOUNT = {
    "account_code": "9999",
    "account_name": "Unknown Destination",
    "account_type": "asset",
}


@dataclass(frozen=True)
class RuleEngineResult:
    proposed_entry: dict
    explanation: str
    requires_human_review: bool
    clarification_reason: str | None


def _coerce_amount(value) -> float | None:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount if amount > 0 else None


def _resolve_amount(message: dict) -> float | None:
    amount = _coerce_amount(message.get("amount"))
    if amount is not None:
        return amount

    entities = dict(message.get("entities") or {})
    amount = _coerce_amount(entities.get("amount"))
    if amount is not None:
        return amount

    amount_mentions = list(message.get("amount_mentions") or [])
    if len(amount_mentions) == 1:
        return _coerce_amount(amount_mentions[0].get("value"))
    return None


def _entry_metadata(message: dict, *, confidence: float, origin_tier: int) -> dict:
    transaction_date = str(message.get("transaction_date") or date.today())
    description = (
        message.get("input_text")
        or message.get("description")
        or message.get("normalized_text")
        or "Autobook generated entry"
    )
    entry = {
        "date": transaction_date,
        "description": str(description),
        "origin_tier": origin_tier,
        "confidence": confidence,
        "rationale": None,
    }
    if message.get("transaction_id") is not None:
        entry["transaction_id"] = message.get("transaction_id")
    return entry


def _build_lines(debit: tuple[str, str], credit: tuple[str, str], amount: float) -> list[dict]:
    return [
        {
            "account_code": debit[0],
            "account_name": debit[1],
            "type": "debit",
            "amount": amount,
            "line_order": 0,
        },
        {
            "account_code": credit[0],
            "account_name": credit[1],
            "type": "credit",
            "amount": amount,
            "line_order": 1,
        },
    ]


def build_rule_based_entry(message: dict, *, confidence: float, origin_tier: int) -> RuleEngineResult:
    amount = _resolve_amount(message)
    intent_label = str(message.get("intent_label") or "").strip().lower() or None
    bank_category = str(message.get("bank_category") or "").strip().lower() or None
    entities = dict(message.get("entities") or {})
    transfer_destination = str(entities.get("transfer_destination") or "").strip() or None

    if amount is None:
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": [],
            },
            explanation="Amount is missing or ambiguous, so the rule engine cannot build balanced journal lines yet.",
            requires_human_review=True,
            clarification_reason="Amount is missing or ambiguous.",
        )

    if intent_label == "asset_purchase" or bank_category == "equipment":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("1500", "Equipment"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Equipment and Cash from the detected asset-purchase intent.",
            requires_human_review=False,
            clarification_reason=None,
        )

    if intent_label == "software_subscription" or bank_category == "software_subscription":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("5300", "Software & Subscriptions"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Software & Subscriptions and Cash from the subscription intent.",
            requires_human_review=False,
            clarification_reason=None,
        )

    if intent_label == "rent_expense" or bank_category == "rent":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("5200", "Rent Expense"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Rent Expense and Cash from the rent intent.",
            requires_human_review=False,
            clarification_reason=None,
        )

    if intent_label == "meals_entertainment" or bank_category == "meals_entertainment":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("5400", "Meals & Entertainment"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Meals & Entertainment and Cash from the meals intent.",
            requires_human_review=False,
            clarification_reason=None,
        )

    if intent_label == "professional_fees" or bank_category == "professional_fees":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("5430", "Professional Fees"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Professional Fees and Cash from the services intent.",
            requires_human_review=False,
            clarification_reason=None,
        )

    if intent_label == "bank_fee" or bank_category == "bank_fees":
        return RuleEngineResult(
            proposed_entry={
                "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
                "lines": _build_lines(("5500", "Bank Fees"), ("1000", "Cash"), amount),
            },
            explanation="Rule engine mapped the transaction to Bank Fees and Cash from the bank-fee classification.",
            requires_human_review=False,
            clarification_reason=None,
        )

    clarification_reason = "Transfer destination account is not confidently mapped."
    if transfer_destination is None:
        clarification_reason = "Destination account is unclear."

    return RuleEngineResult(
        proposed_entry={
            "entry": _entry_metadata(message, confidence=confidence, origin_tier=origin_tier),
            "lines": _build_lines(
                (UNKNOWN_DESTINATION_ACCOUNT["account_code"], UNKNOWN_DESTINATION_ACCOUNT["account_name"]),
                ("1000", "Cash"),
                amount,
            ),
        },
        explanation=(
            "Rule engine prepared a fallback transfer-style journal entry using Unknown Destination because the "
            "destination account still needs confirmation."
        ),
        requires_human_review=True,
        clarification_reason=clarification_reason,
    )
