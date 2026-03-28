from pydantic import BaseModel


class LedgerSummary(BaseModel):
    total_debits: float
    total_credits: float


class LedgerResponse(BaseModel):
    entries: list[dict]
    balances: list[dict]
    summary: LedgerSummary
