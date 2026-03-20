from fastapi import APIRouter

from config import get_settings
from schemas.ledger import LedgerResponse, LedgerSummary

router = APIRouter(prefix="/api/v1")


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger():
    # TODO: replace with DB query
    return LedgerResponse(
        entries=[
            {
                "journal_entry_id": "je_001",
                "date": "2026-03-19",
                "description": "Office Supplies",
                "status": "auto_posted",
                "origin_tier": 1,
                "confidence": {"overall": 0.97, "auto_post_threshold": get_settings().AUTO_POST_THRESHOLD},
                "lines": [
                    {"account_code": "6100", "account_name": "Office Supplies", "type": "debit", "amount": 49.99},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 49.99},
                ],
            },
            {
                "journal_entry_id": "je_002",
                "date": "2026-03-18",
                "description": "Laptop Purchase",
                "status": "auto_posted",
                "origin_tier": 2,
                "confidence": {"overall": 0.92, "auto_post_threshold": get_settings().AUTO_POST_THRESHOLD},
                "lines": [
                    {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 2400},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 2400},
                ],
            },
        ],
        balances=[
            {"account_code": "1000", "account_name": "Cash", "balance": -2449.99},
            {"account_code": "1500", "account_name": "Equipment", "balance": 2400},
            {"account_code": "6100", "account_name": "Office Supplies", "balance": 49.99},
        ],
        summary=LedgerSummary(total_debits=2449.99, total_credits=2449.99),
    )
