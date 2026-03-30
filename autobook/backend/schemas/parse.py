from pydantic import BaseModel, Field

DEFAULT_STAGES = ["precedent", "ml", "llm"]
DEFAULT_POST_STAGES = ["precedent", "ml", "llm"]


class ParseRequest(BaseModel):
    input_text: str
    source: str = "manual_text"
    currency: str = "CAD"
    stages: list[str] = Field(default_factory=lambda: list(DEFAULT_STAGES))
    store: bool = True
    post_stages: list[str] = Field(default_factory=lambda: list(DEFAULT_POST_STAGES))


class JournalLine(BaseModel):
    account_code: str
    account_name: str
    type: str  # "debit" or "credit"
    amount: float


class ProposedEntry(BaseModel):
    journal_entry_id: str | None = None
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


class ParseAccepted(BaseModel):
    parse_id: str
    status: str = "accepted"
    statement_count: int = 1


class BatchItem(BaseModel):
    child_parse_id: str
    statement_index: int
    input_text: str | None = None
    status: str
    clarification_id: str | None = None
    journal_entry_id: str | None = None
    error: str | None = None


class BatchSummary(BaseModel):
    total_statements: int
    completed_statements: int
    pending_statements: int
    auto_posted_count: int
    needs_clarification_count: int
    resolved_count: int
    rejected_count: int
    failed_count: int
    status: str
    items: list[BatchItem]


class ParseStatusResponse(BaseModel):
    parse_id: str
    status: str
    stage: str | None = None
    occurred_at: str
    updated_at: str
    input_text: str | None = None
    explanation: str | None = None
    confidence: Confidence | None = None
    proposed_entry: ProposedEntry | None = None
    clarification_id: str | None = None
    journal_entry_id: str | None = None
    error: str | None = None
    batch: BatchSummary | None = None
