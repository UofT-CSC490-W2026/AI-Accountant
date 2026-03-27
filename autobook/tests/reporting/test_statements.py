from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from reporting.statements import build_balance_sheet, build_income_statement, build_trial_balance


def _make_account(code, name, account_type):
    return SimpleNamespace(account_code=code, account_name=name, account_type=account_type)


def _make_line(account_code, line_type, amount):
    return SimpleNamespace(account_code=account_code, type=line_type, amount=Decimal(str(amount)))


def _make_entry(lines):
    return SimpleNamespace(lines=lines, status="posted")


ACCOUNTS = [
    _make_account("1000", "Cash", "asset"),
    _make_account("1500", "Equipment", "asset"),
    _make_account("2000", "Accounts Payable", "liability"),
    _make_account("3000", "Common Stock", "equity"),
    _make_account("4000", "Service Revenue", "revenue"),
    _make_account("5000", "Rent Expense", "expense"),
]

ENTRIES = [
    _make_entry([_make_line("1500", "debit", 5000), _make_line("1000", "credit", 5000)]),
    _make_entry([_make_line("1000", "debit", 3000), _make_line("4000", "credit", 3000)]),
    _make_entry([_make_line("5000", "debit", 1000), _make_line("1000", "credit", 1000)]),
]


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_sections(mock_coa, mock_je):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    sections = {s["title"]: s["rows"] for s in result["sections"]}
    assert "Assets" in sections
    assert "Liabilities" in sections
    assert "Equity" in sections


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_net_income(mock_coa, mock_je):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    equity_section = next(s for s in result["sections"] if s["title"] == "Equity")
    earnings_row = next(r for r in equity_section["rows"] if r["label"] == "Current Earnings")
    assert earnings_row["amount"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_balance_sheet_totals(mock_coa, mock_je):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    totals = result["totals"]
    assert totals["total_assets"] == 2000.0
    assert totals["total_liabilities"] == 0.0
    assert totals["total_equity"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=[])
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_balance_sheet_empty(mock_coa, mock_je):
    result = build_balance_sheet(MagicMock(), "user-1", "2026-03-23")
    for section in result["sections"]:
        assert section["rows"] == []
    assert result["totals"]["total_assets"] == 0.0


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_income_statement_sections(mock_coa, mock_je):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    sections = {s["title"]: s["rows"] for s in result["sections"]}
    assert "Revenue" in sections
    assert "Expenses" in sections
    assert any(r["label"] == "Service Revenue" for r in sections["Revenue"])
    assert any(r["label"] == "Rent Expense" for r in sections["Expenses"])


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_income_statement_net_income(mock_coa, mock_je):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_revenue"] == 3000.0
    assert result["totals"]["total_expenses"] == 1000.0
    assert result["totals"]["net_income"] == 2000.0


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=[])
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=[])
def test_income_statement_empty(mock_coa, mock_je):
    result = build_income_statement(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["net_income"] == 0.0
    assert result["totals"]["total_revenue"] == 0.0


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_trial_balance_columns(mock_coa, mock_je):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    rows = result["sections"][0]["rows"]
    assert len(rows) == 4
    for row in rows:
        assert "label" in row
        assert "amount" in row


@patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=ENTRIES)
@patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=ACCOUNTS)
def test_trial_balance_balanced(mock_coa, mock_je):
    result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_debits"] == result["totals"]["total_credits"]
    assert result["totals"]["total_debits"] == 6000.0


def test_trial_balance_negative_liability_balance():
    """Liability with more debits than credits → debit column in trial balance."""
    accounts = [
        _make_account("2000", "Accounts Payable", "liability"),
        _make_account("1000", "Cash", "asset"),
    ]
    entries = [
        _make_entry([
            _make_line("2000", "debit", 500),
            _make_line("1000", "credit", 500),
        ]),
    ]
    with patch("reporting.statements.JournalEntryDAO.list_by_user", return_value=entries), \
         patch("reporting.statements.ChartOfAccountsDAO.list_by_user", return_value=accounts):
        result = build_trial_balance(MagicMock(), "user-1", "2026-03-23")
    assert result["totals"]["total_debits"] == 500.0
    assert result["totals"]["total_credits"] == 500.0
