from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_current_local_user
from db.connection import get_db
from db.dao.journal_entries import JournalEntryDAO
from db.models.journal import JournalEntry
from schemas.ledger import LedgerResponse, LedgerSummary

router = APIRouter(prefix="/api/v1")


def _to_float(value) -> float:
    return float(value if isinstance(value, Decimal) else value or 0)


def _serialize_entry(entry: JournalEntry) -> dict:
    return {
        "journal_entry_id": str(entry.id),
        "date": str(entry.date),
        "description": entry.description,
        "status": entry.status,
        "origin_tier": entry.origin_tier,
        "confidence": {
            "overall": _to_float(entry.confidence),
        }
        if entry.confidence is not None
        else None,
        "lines": [
            {
                "account_code": line.account_code,
                "account_name": line.account_name,
                "type": line.type,
                "amount": _to_float(line.amount),
            }
            for line in entry.lines
        ],
    }


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_local_user),
):
    entries = JournalEntryDAO.list_by_user(db, current_user.id)
    balances = JournalEntryDAO.compute_balances(db, current_user.id)
    summary = JournalEntryDAO.compute_summary(db, current_user.id)

    return LedgerResponse(
        entries=[_serialize_entry(entry) for entry in entries],
        balances=[
            {
                "account_code": item["account_code"],
                "account_name": item["account_name"],
                "balance": _to_float(item["balance"]),
            }
            for item in balances
        ],
        summary=LedgerSummary(
            total_debits=_to_float(summary.get("total_debits")),
            total_credits=_to_float(summary.get("total_credits")),
        ),
    )
