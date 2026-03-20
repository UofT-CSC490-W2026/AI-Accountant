from pydantic import BaseModel


class Period(BaseModel):
    as_of: str


class StatementResponse(BaseModel):
    statement_type: str  # "balance_sheet", "income_statement", "trial_balance"
    period: Period
    sections: list[dict]
    totals: dict
