from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from reporting.statements import build_balance_sheet, build_income_statement, build_trial_balance


def _make_account(code, name, account_type):
    return SimpleNamespace(account_code=code, account_name=name, account_type=account_type)


ACCOUNTS = [
    _make_account("1000", "Cash", "asset"),
    _make_account("1500", "Equipment", "asset"),
    _make_account("2000", "Accounts Payable", "liability"),
    _make_account("3000", "Common Stock", "equity"),
    _make_account("4000", "Service Revenue", "revenue"),
    _make_account("5000", "Rent Expense", "expense"),
]

BALANCES = [
    {
        "account_code": "1000",
        "account_name": "Cash",
        "account_type": "asset",
        "debit_total": Decimal("0"),
        "credit_total": Decimal("3000"),
        "balance": Decimal("-3000"),
    },
    {
        "account_code": "1500",
        "account_name": "Equipment",
        "account_type": "asset",
        "debit_total": Decimal("5000"),
        "credit_total": Decimal("0"),
        "balance": Decimal("5000"),
    },
    {
        "account_code": "4000",
        "account_name": "Service Revenue",
        "account_type": "revenue",
        "debit_total": Decimal("0"),
        "credit_total": Decimal("3000"),
        "balance": Decimal("3000"),
    },
    {
        "account_code": "5000",
        "account_name": "Rent Expense",
        "account_type": "expense",
        "debit_total": Decimal("1000"),
        "credit_total": Decimal("0"),
        "balance": Decimal("1000"),
    },
]

@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_sections(mock_coa, mock_balances):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    sections = {s["title"]: s["rows"] for s in result["sections"]}
    assert "Assets" in sections
    assert "Liabilities" in sections
    assert "Equity" in sections


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_net_income(mock_coa, mock_balances):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    equity_section = next(s for s in result["sections"] if s["title"] == "Equity")
    earnings_row = next(r for r in equity_section["rows"] if r["label"] == "Current Earnings")
    assert earnings_row["amount"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_totals(mock_coa, mock_balances):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    totals = result["totals"]
    assert totals["total_assets"] == 2000.0
    assert totals["total_liabilities"] == 0.0
    assert totals["total_equity"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=[])
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_balance_sheet_empty(mock_coa, mock_balances):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    for section in result["sections"]:
        assert section["rows"] == []
    assert result["totals"]["total_assets"] == 0.0


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_income_statement_sections(mock_coa, mock_balances):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    sections = {s["title"]: s["rows"] for s in result["sections"]}
    assert "Revenue" in sections
    assert "Expenses" in sections
    assert any(r["label"] == "Service Revenue" for r in sections["Revenue"])
    assert any(r["label"] == "Rent Expense" for r in sections["Expenses"])


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_income_statement_net_income(mock_coa, mock_balances):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_revenue"] == 3000.0
    assert result["totals"]["total_expenses"] == 1000.0
    assert result["totals"]["net_income"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=[])
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_income_statement_empty(mock_coa, mock_balances):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["net_income"] == 0.0
    assert result["totals"]["total_revenue"] == 0.0


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_trial_balance_columns(mock_coa, mock_balances):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    rows = result["sections"][0]["rows"]
    assert len(rows) == 4
    for row in rows:
        assert "label" in row
        assert "amount" in row
        assert "debit" in row
        assert "credit" in row


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_trial_balance_balanced(mock_coa, mock_balances):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_debits"] == result["totals"]["total_credits"]
    assert result["totals"]["total_debits"] == 6000.0


def test_trial_balance_negative_liability_balance():
    accounts = [
        _make_account("2000", "Accounts Payable", "liability"),
        _make_account("1000", "Cash", "asset"),
    ]
    balances = [
        {
            "account_code": "2000",
            "account_name": "Accounts Payable",
            "account_type": "liability",
            "debit_total": Decimal("500"),
            "credit_total": Decimal("0"),
            "balance": Decimal("-500"),
        },
        {
            "account_code": "1000",
            "account_name": "Cash",
            "account_type": "asset",
            "debit_total": Decimal("0"),
            "credit_total": Decimal("500"),
            "balance": Decimal("-500"),
        },
    ]
    with patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=balances), \
         patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=accounts):
        result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_debits"] == 500.0
    assert result["totals"]["total_credits"] == 500.0


def test_balance_sheet_uses_same_posted_balance_filters_as_ledger():
    with patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=[]) as mock_balances, \
         patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[]):
        build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    assert mock_balances.call_args.kwargs["filters"] == {
        "date_to": date(2026, 3, 23),
        "status": "posted",
    }


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=BALANCES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_trial_balance_falls_back_to_balance_metadata_when_chart_rows_are_missing(
    mock_coa,
    mock_balances,
):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    rows = result["sections"][0]["rows"]
    assert any(row["label"] == "1500 Equipment" and row["amount"] == 5000.0 for row in rows)
    assert any(row["label"] == "1000 Cash" and row["amount"] == 3000.0 for row in rows)


@patch("reporting.statements.JournalEntryDAO.compute_balances", return_value=[
    {
        "account_code": "1000",
        "account_name": "Cash",
        "account_type": "asset",
        "debit_total": Decimal("500"),
        "credit_total": Decimal("500"),
        "balance": Decimal("0"),
    }
])
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_trial_balance_keeps_rows_when_activity_nets_to_zero(mock_coa, mock_balances):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    rows = result["sections"][0]["rows"]
    assert rows == [
        {
            "label": "1000 Cash",
            "debit": 500.0,
            "credit": 500.0,
            "amount": 500.0,
        }
    ]
    assert result["totals"] == {"total_debits": 500.0, "total_credits": 500.0}
