from __future__ import annotations

from datetime import date, datetime, timezone
from pydantic import BaseModel, Field


class CanonicalTransaction(BaseModel):
    transaction_id: str = Field(..., description="Stable ID derived from source fields (hash).")
    raw_description: str
    normalized_description: str
    amount: float
    currency: str = "CAD"
    transaction_date: date
    counterparty: str | None = None
    source_system: str = Field(..., description="e.g., 'bank_csv', 'stripe_csv'")
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
