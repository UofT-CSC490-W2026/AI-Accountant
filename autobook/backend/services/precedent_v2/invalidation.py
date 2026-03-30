"""Event-driven invalidation — outside the pipeline.

Called when chart of accounts or tax structure changes.
Removes affected precedent entries so stale patterns aren't reused.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from services.precedent_v2.dao import PrecedentDAO


def on_coa_change(db: Session, user_id, affected_account_codes: list[str]) -> int:
    """Invalidate precedent entries referencing changed accounts.

    Called when a user modifies their chart of accounts.

    Returns:
        Number of entries invalidated.
    """
    return PrecedentDAO.invalidate_by_accounts(db, user_id, affected_account_codes)


def on_tax_change(db: Session, user_id, affected_tax_codes: list[str]) -> int:
    """Invalidate precedent entries that include affected tax lines.

    Called when tax structure changes (rate change, new tax type, etc.).
    Tax lines are always recomputed on bypass, but the structure_hash
    includes tax line positions — so entries with the old tax structure
    should be invalidated to prevent stale matching.

    Returns:
        Number of entries invalidated.
    """
    return PrecedentDAO.invalidate_by_accounts(db, user_id, affected_tax_codes)
