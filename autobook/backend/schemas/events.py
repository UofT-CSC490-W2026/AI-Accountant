from pydantic import BaseModel


class RealtimeEvent(BaseModel):
    type: str  # "accounting.snapshot.updated"
    reason: str  # "journal_entry.posted", "clarification.queued", "clarification.resolved", "clarification.rejected"
    journal_entry_id: str
    occurred_at: str
