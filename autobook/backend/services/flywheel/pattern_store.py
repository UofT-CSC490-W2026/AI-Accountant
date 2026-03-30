"""Write to PG pattern store via PrecedentDAO.

Called on T2+ resolutions.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from services.precedent_v2.dao import PrecedentDAO
from services.precedent_v2.vendor import normalize_vendor

logger = logging.getLogger(__name__)


def write_pattern(db: Session, user_id, message: dict) -> None:
    """Extract structure/ratio from proposed_entry and write to precedent_entries."""
    vendor = normalize_vendor(message.get("counterparty") or message.get("vendor") or "")
    if not vendor:
        logger.debug("No vendor — skipping pattern store write")
        return

    amount = message.get("amount")
    if not amount or float(amount) <= 0:
        logger.debug("No positive amount — skipping pattern store write")
        return

    proposed_entry = message.get("proposed_entry")
    if not proposed_entry:
        logger.debug("No proposed_entry — skipping pattern store write")
        return

    lines = proposed_entry.get("lines", [])
    if not lines:
        return

    structure = {"lines": [
        {"account_code": line.get("account_code", ""), "side": line.get("type", "")}
        for line in lines
    ]}
    ratio = {"lines": [
        {"account_code": line.get("account_code", ""), "ratio": _safe_ratio(line, amount)}
        for line in lines
    ]}

    journal_entry_id = message.get("journal_entry_id")

    PrecedentDAO.insert(
        db=db,
        user_id=user_id,
        vendor=vendor,
        amount=Decimal(str(amount)),
        structure=structure,
        ratio=ratio,
        source_journal_entry_id=journal_entry_id,
    )


def _safe_ratio(line: dict, total_amount) -> float:
    try:
        return round(float(line.get("amount", 0)) / float(total_amount), 6)
    except (ZeroDivisionError, TypeError, ValueError):
        return 0.0
