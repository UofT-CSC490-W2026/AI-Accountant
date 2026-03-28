from pydantic import BaseModel

from schemas.parse import Confidence, ProposedEntry


class ClarificationItem(BaseModel):
    clarification_id: str
    status: str  # "pending", "resolved", "rejected"
    source_text: str
    explanation: str
    confidence: Confidence
    proposed_entry: ProposedEntry


class ClarificationsResponse(BaseModel):
    items: list[ClarificationItem]
    count: int


class ResolveRequest(BaseModel):
    action: str  # "approve" or "reject"
    edited_entry: ProposedEntry | None = None


class ResolveResponse(BaseModel):
    clarification_id: str
    status: str
    journal_entry_id: str | None = None
