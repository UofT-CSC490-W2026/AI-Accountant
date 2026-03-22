from fastapi import APIRouter, Depends

from auth.deps import AuthContext, get_current_user, require_role
from auth.schemas import UserRole
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
async def get_clarifications(current_user: AuthContext = Depends(get_current_user)):
    # TODO: replace with DB query
    items = [
        ClarificationItem(
            clarification_id="cl_stub_001",
            status="pending",
            source_text="[BACKEND STUB] Transferred money",
            explanation="[BACKEND STUB] Transfer direction is unclear.",
            confidence=Confidence(overall=0.66, auto_post_threshold=get_settings().AUTO_POST_THRESHOLD),
            proposed_entry=ProposedEntry(journal_entry_id="je_stub_pending_001", lines=[]),
        ),
        ClarificationItem(
            clarification_id="cl_stub_002",
            status="pending",
            source_text="[BACKEND STUB] Paid for team lunch",
            explanation="[BACKEND STUB] Could be meals & entertainment or employee benefits.",
            confidence=Confidence(overall=0.66, auto_post_threshold=get_settings().AUTO_POST_THRESHOLD),
            proposed_entry=ProposedEntry(
                journal_entry_id="je_stub_pending_002",
                lines=[
                    JournalLine(account_code="6200", account_name="Meals & Entertainment", type="debit", amount=666.00),
                    JournalLine(account_code="1000", account_name="Cash", type="credit", amount=666.00),
                ],
            ),
        ),
    ]
    return ClarificationsResponse(items=items, count=len(items))


@router.post("/clarifications/{clarification_id}/resolve", response_model=ResolveResponse)
async def resolve_clarification(
    clarification_id: str,
    body: ResolveRequest,
    current_user: AuthContext = Depends(require_role(UserRole.MANAGER)),
):
    # TODO: replace with DB query
    return ResolveResponse(
        clarification_id=clarification_id,
        status="resolved" if body.action == "approve" else "rejected",
        journal_entry_id="je_stub_666" if body.action == "approve" else None,
    )
