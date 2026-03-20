from fastapi import APIRouter

from schemas.clarifications import (
    ClarificationItem,
    ClarificationsResponse,
    ResolveRequest,
    ResolveResponse,
)
from config import get_settings
from schemas.parse import Confidence, JournalLine, ProposedEntry

router = APIRouter(prefix="/api/v1")


@router.get("/clarifications", response_model=ClarificationsResponse)
async def get_clarifications():
    # TODO: replace with DB query
    items = [
        ClarificationItem(
            clarification_id="cl_001",
            status="pending",
            source_text="Transferred money",
            explanation="Transfer direction is unclear.",
            confidence=Confidence(overall=0.51, auto_post_threshold=get_settings().AUTO_POST_THRESHOLD),
            proposed_entry=ProposedEntry(journal_entry_id="je_pending_001", lines=[]),
        ),
        ClarificationItem(
            clarification_id="cl_002",
            status="pending",
            source_text="Paid for team lunch",
            explanation="Could be meals & entertainment or employee benefits.",
            confidence=Confidence(overall=0.62, auto_post_threshold=get_settings().AUTO_POST_THRESHOLD),
            proposed_entry=ProposedEntry(
                journal_entry_id="je_pending_002",
                lines=[
                    JournalLine(account_code="6200", account_name="Meals & Entertainment", type="debit", amount=150),
                    JournalLine(account_code="1000", account_name="Cash", type="credit", amount=150),
                ],
            ),
        ),
    ]
    return ClarificationsResponse(items=items, count=len(items))


@router.post("/clarifications/{clarification_id}/resolve", response_model=ResolveResponse)
async def resolve_clarification(clarification_id: str, body: ResolveRequest):
    # TODO: replace with DB query
    return ResolveResponse(
        clarification_id=clarification_id,
        status="resolved" if body.action == "approve" else "rejected",
        journal_entry_id="je_456" if body.action == "approve" else None,
    )
