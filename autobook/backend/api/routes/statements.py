from fastapi import APIRouter, Query

from schemas.statements import StatementResponse, Period

router = APIRouter(prefix="/api/v1")


@router.get("/statements", response_model=StatementResponse)
async def get_statements(
    statement_type: str = Query(default="balance_sheet"),
    as_of: str = Query(default="2026-03-31"),
):
    # TODO: replace with DB query
    if statement_type == "income_statement":
        return StatementResponse(
            statement_type="income_statement",
            period=Period(as_of=as_of),
            sections=[
                {
                    "name": "Revenue",
                    "lines": [
                        {"account_code": "4000", "account_name": "Sales Revenue", "amount": 12000},
                    ],
                },
                {
                    "name": "Expenses",
                    "lines": [
                        {"account_code": "6100", "account_name": "Office Supplies", "amount": 49.99},
                        {"account_code": "6200", "account_name": "Meals & Entertainment", "amount": 150},
                    ],
                },
            ],
            totals={"total_revenue": 12000, "total_expenses": 199.99, "net_income": 11800.01},
        )

    return StatementResponse(
        statement_type="balance_sheet",
        period=Period(as_of=as_of),
        sections=[
            {
                "name": "Assets",
                "lines": [
                    {"account_code": "1000", "account_name": "Cash", "amount": 9550.01},
                    {"account_code": "1500", "account_name": "Equipment", "amount": 2400},
                ],
            },
            {
                "name": "Liabilities",
                "lines": [],
            },
            {
                "name": "Equity",
                "lines": [
                    {"account_code": "3000", "account_name": "Retained Earnings", "amount": 11950.01},
                ],
            },
        ],
        totals={"total_assets": 11950.01, "total_liabilities": 0, "total_equity": 11950.01},
    )
