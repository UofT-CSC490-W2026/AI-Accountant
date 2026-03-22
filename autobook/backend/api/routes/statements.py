from fastapi import APIRouter, Depends, Query

from auth.deps import AuthContext, get_current_user
from schemas.statements import StatementResponse, Period

router = APIRouter(prefix="/api/v1")


@router.get("/statements", response_model=StatementResponse)
async def get_statements(
    statement_type: str = Query(default="balance_sheet"),
    as_of: str = Query(default="2026-03-31"),
    current_user: AuthContext = Depends(get_current_user),
):
    # TODO: replace with DB query
    if statement_type == "income_statement":
        return StatementResponse(
            statement_type="income_statement",
            period=Period(as_of=as_of),
            sections=[
                {
                    "title": "Revenue",
                    "rows": [
                        {"label": "[BACKEND STUB] Sales Revenue", "amount": 6660.00},
                    ],
                },
                {
                    "title": "Expenses",
                    "rows": [
                        {"label": "[BACKEND STUB] Office Supplies", "amount": 66.60},
                        {"label": "[BACKEND STUB] Meals & Entertainment", "amount": 666.00},
                    ],
                },
            ],
            totals={"total_revenue": 6660.00, "total_expenses": 732.60, "net_income": 5927.40},
        )

    return StatementResponse(
        statement_type="balance_sheet",
        period=Period(as_of=as_of),
        sections=[
            {
                "title": "Assets",
                "rows": [
                    {"label": "[BACKEND STUB] Cash", "amount": 5927.40},
                    {"label": "[BACKEND STUB] Equipment", "amount": 666.00},
                ],
            },
            {
                "title": "Liabilities",
                "rows": [],
            },
            {
                "title": "Equity",
                "rows": [
                    {"label": "[BACKEND STUB] Retained Earnings", "amount": 6593.40},
                ],
            },
        ],
        totals={"total_assets": 6593.40, "total_liabilities": 0, "total_equity": 6593.40},
    )
