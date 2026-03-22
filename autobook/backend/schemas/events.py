from pydantic import BaseModel


class RealtimeEvent(BaseModel):
    type: str  # "entry.posted", "clarification.created", "clarification.resolved"
    journal_entry_id: str | None = None
    parse_id: str | None = None
    user_id: str | None = None
    input_text: str | None = None
    confidence: dict | None = None
    explanation: str | None = None
    status: str | None = None
    proposed_entry: dict | None = None
    parse_time_ms: int | None = None
    occurred_at: str
