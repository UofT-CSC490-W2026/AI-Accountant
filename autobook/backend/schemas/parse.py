from pydantic import BaseModel


class ParseRequest(BaseModel):
    input_text: str
    source: str = "manual"
    currency: str = "CAD"


class JournalLine(BaseModel):
    account_code: str
    account_name: str
    type: str  # "debit" or "credit"
    amount: float


class ProposedEntry(BaseModel):
    journal_entry_id: str
    lines: list[JournalLine]


class Confidence(BaseModel):
    overall: float
    auto_post_threshold: float


class ParseResponse(BaseModel):
    parse_id: str
    status: str  # "auto_posted" or "needs_clarification"
    explanation: str
    confidence: Confidence
    parse_time_ms: int
    proposed_entry: ProposedEntry
    clarification_id: str | None = None
