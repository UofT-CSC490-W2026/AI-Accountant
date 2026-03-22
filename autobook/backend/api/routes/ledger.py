from fastapi import APIRouter, Depends

from auth.deps import AuthContext, get_current_user
from config import get_settings
from schemas.ledger import LedgerResponse, LedgerSummary

router = APIRouter(prefix="/api/v1")


@router.get("/ledger", response_model=LedgerResponse)
async def get_ledger(current_user: AuthContext = Depends(get_current_user)):
    # TODO: replace with DB query
    return LedgerResponse(
        entries=[
            {
                "journal_entry_id": "je_stub_001",
                "date": "2026-06-06",
                "description": "[BACKEND STUB] Equipment Purchase",
                "status": "auto_posted",
                "origin_tier": 1,
                "confidence": {"overall": 0.66, "auto_post_threshold": get_settings().AUTO_POST_THRESHOLD},
                "lines": [
                    {"account_code": "1500", "account_name": "Equipment", "type": "debit", "amount": 666.00},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 666.00},
                ],
            },
            {
                "journal_entry_id": "je_stub_002",
                "date": "2026-06-05",
                "description": "[BACKEND STUB] Office Supplies",
                "status": "auto_posted",
                "origin_tier": 2,
                "confidence": {"overall": 0.96, "auto_post_threshold": get_settings().AUTO_POST_THRESHOLD},
                "lines": [
                    {"account_code": "6100", "account_name": "Office Supplies", "type": "debit", "amount": 66.60},
                    {"account_code": "1000", "account_name": "Cash", "type": "credit", "amount": 66.60},
                ],
            },
        ],
        balances=[
            {"account_code": "1000", "account_name": "Cash", "balance": -732.60},
            {"account_code": "1500", "account_name": "Equipment", "balance": 666.00},
            {"account_code": "6100", "account_name": "Office Supplies", "balance": 66.60},
        ],
        summary=LedgerSummary(total_debits=732.60, total_credits=732.60),
    )
