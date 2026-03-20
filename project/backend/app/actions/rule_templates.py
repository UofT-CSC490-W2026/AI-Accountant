"""Journal-entry template functions (§1.1) — one per intent.

Each function accepts a DB session, an org_id, and the relevant
business-event parameters. It resolves accounts from the CoA, builds
the correct debit/credit lines, and delegates to
``journal_entries.create_journal_entry`` (which enforces balance).

Functions that produce side-effects beyond a journal entry (e.g.
creating a corporate document or scheduling future entries) do so
within the same session so callers can commit atomically.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.actions.accounts import get_account_by_number, get_or_create_account
from app.actions.assets import calculate_annual_cca, create_asset, dispose_asset
from app.actions.documents import create_corporate_document
from app.actions.errors import NotFoundError, ValidationError
from app.actions.journal_entries import create_journal_entry, reverse_journal_entry
from app.actions.schedules import create_scheduled_entry
from app.actions.shareholder_loans import create_shareholder_loan_transaction
from app.actions.tax import create_tax_obligation
from app.models.enums import (
    DocumentType,
    JournalEntrySource,
    JournalEntryStatus,
    ScheduleFrequency,
    ScheduleSource,
    TaxType,
)
from app.models.journal import JournalEntry


def _require_account(db: Session, org_id: uuid.UUID, number: str) -> uuid.UUID:
    """Look up an account by number, raising NotFoundError if missing."""
    acct = get_account_by_number(db, org_id=org_id, account_number=number)
    if acct is None:
        raise NotFoundError(
            f"account {number} not found for org {org_id} — "
            "run seed_chart_of_accounts first"
        )
    return acct.id


# ─────────────────────────────────────────────────────────────────
# 1.  record_operating_expense  (§1.1)
# ─────────────────────────────────────────────────────────────────


def record_operating_expense(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    expense_category: str,
    entry_date: date,
    vendor: str | None = None,
    tax_amount: Decimal | None = None,
    pay_with: str = "1000",
) -> JournalEntry:
    """Dr Expense, Cr Cash/AP.  Optionally splits out HST ITC."""
    expense_account = get_or_create_account(db, org_id=org_id, category=expense_category)
    cash_id = _require_account(db, org_id, pay_with)

    lines: list[dict] = [
        {"account_id": expense_account.id, "debit_amount": amount},
        {"account_id": cash_id, "credit_amount": amount},
    ]

    if tax_amount is not None and tax_amount > 0:
        if tax_amount >= amount:
            raise ValidationError("tax_amount must be less than amount")
        itc_id = _require_account(db, org_id, "2150")
        lines[0]["debit_amount"] = amount - tax_amount
        lines.append({"account_id": itc_id, "debit_amount": tax_amount})

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Operating expense{f': {vendor}' if vendor else ''}",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )


# ─────────────────────────────────────────────────────────────────
# 2.  record_capital_expenditure  (§1.1 + §1.2)
# ─────────────────────────────────────────────────────────────────


def record_capital_expenditure(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    asset_name: str,
    entry_date: date,
    cca_class: str,
    asset_account_number: str = "1500",
    pay_with: str = "1000",
    tax_amount: Decimal | None = None,
    description: str | None = None,
) -> dict:
    """Record a capital asset purchase and optionally compute first-year CCA.

    Returns dict with ``journal_entry``, ``asset``, and ``cca_entry``.
    """
    asset_acct_id = _require_account(db, org_id, asset_account_number)
    cash_id = _require_account(db, org_id, pay_with)

    lines: list[dict] = [
        {"account_id": asset_acct_id, "debit_amount": amount},
        {"account_id": cash_id, "credit_amount": amount},
    ]
    if tax_amount is not None and tax_amount > 0:
        if tax_amount >= amount:
            raise ValidationError("tax_amount must be less than amount")
        itc_id = _require_account(db, org_id, "2150")
        lines[0]["debit_amount"] = amount - tax_amount
        lines.append({"account_id": itc_id, "debit_amount": tax_amount})

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=description or f"Capital expenditure: {asset_name}",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )

    asset = create_asset(
        db,
        org_id=org_id,
        name=asset_name,
        acquisition_date=entry_date,
        acquisition_cost=amount - (tax_amount or Decimal("0")),
        cca_class=cca_class,
    )

    cca_entry = calculate_annual_cca(
        db,
        asset_id=asset.id,
        fiscal_year=entry_date.year,
        journal_entry_id=je.id,
    )

    return {"journal_entry": je, "asset": asset, "cca_entry": cca_entry}


# ─────────────────────────────────────────────────────────────────
# 3.  record_revenue_onetime  (§1.1)
# ─────────────────────────────────────────────────────────────────


def record_revenue_onetime(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    description: str | None = None,
    revenue_account_number: str = "4000",
    receive_into: str = "1000",
    tax_collected: Decimal | None = None,
) -> JournalEntry:
    """Dr Cash/AR, Cr Revenue.  Optionally records HST collected."""
    cash_id = _require_account(db, org_id, receive_into)
    revenue_id = _require_account(db, org_id, revenue_account_number)

    lines: list[dict] = [
        {"account_id": cash_id, "debit_amount": amount},
        {"account_id": revenue_id, "credit_amount": amount},
    ]

    if tax_collected is not None and tax_collected > 0:
        hst_payable_id = _require_account(db, org_id, "2100")
        lines[1]["credit_amount"] = amount - tax_collected
        lines.append({"account_id": hst_payable_id, "credit_amount": tax_collected})

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=description or "Revenue received",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )


# ─────────────────────────────────────────────────────────────────
# 4.  record_subscription_revenue  (§1.1 + §1.3 proration)
# ─────────────────────────────────────────────────────────────────


def record_subscription_revenue(
    db: Session,
    *,
    org_id: uuid.UUID,
    total_amount: Decimal,
    start_date: date,
    end_date: date,
    description: str | None = None,
    receive_into: str = "1000",
    revenue_account_number: str = "4000",
) -> dict:
    """Record upfront cash receipt as Deferred Revenue, then schedule
    monthly revenue-recognition entries (proration engine §1.3).

    Returns dict with ``receipt_entry`` and ``scheduled_entry``.
    """
    cash_id = _require_account(db, org_id, receive_into)
    deferred_id = _require_account(db, org_id, "2300")
    revenue_id = _require_account(db, org_id, revenue_account_number)

    receipt = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=start_date,
        description=description or "Subscription payment received (deferred)",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": cash_id, "debit_amount": total_amount},
            {"account_id": deferred_id, "credit_amount": total_amount},
        ],
    )

    # Build proration schedule
    months = _months_between(start_date, end_date)
    total_days = (end_date - start_date).days or 1
    monthly_template_lines = []
    for m_start, m_end in months:
        days_in_month = (m_end - m_start).days
        month_amount = (total_amount * days_in_month / total_days).quantize(
            Decimal("0.01")
        )
        monthly_template_lines.append(
            {
                "debit_account": "2300",
                "credit_account": revenue_account_number,
                "amount": str(month_amount),
                "date": m_end.isoformat(),
            }
        )

    scheduled = create_scheduled_entry(
        db,
        org_id=org_id,
        template_journal_entry={
            "lines": monthly_template_lines,
            "description": description or "Subscription revenue recognition",
        },
        frequency=ScheduleFrequency.MONTHLY,
        start_date=start_date,
        end_date=end_date,
        next_run_date=months[0][1] if months else start_date,
        source=ScheduleSource.DEFERRED_REVENUE,
    )

    return {"receipt_entry": receipt, "scheduled_entry": scheduled}


def _months_between(
    start: date, end: date
) -> list[tuple[date, date]]:
    """Return a list of (month_start, month_end) tuples."""
    result: list[tuple[date, date]] = []
    current = start
    while current < end:
        # End of this month
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1, day=1)
        else:
            next_month = current.replace(month=current.month + 1, day=1)
        month_end = min(next_month - timedelta(days=1), end)
        result.append((current, month_end))
        current = next_month
    return result


# ─────────────────────────────────────────────────────────────────
# 5.  record_refund  (§1.1)
# ─────────────────────────────────────────────────────────────────


def record_refund(
    db: Session,
    *,
    org_id: uuid.UUID,
    original_journal_entry_id: uuid.UUID,
    refund_date: date,
    created_by: str | None = None,
) -> JournalEntry:
    """Create a reversal entry for the original sale/revenue entry."""
    return reverse_journal_entry(
        db,
        journal_entry_id=original_journal_entry_id,
        reversal_date=refund_date,
        created_by=created_by,
    )


# ─────────────────────────────────────────────────────────────────
# 6.  record_inventory_purchase
# ─────────────────────────────────────────────────────────────────


def record_inventory_purchase(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    vendor: str | None = None,
    pay_with: str = "1000",
    tax_amount: Decimal | None = None,
) -> JournalEntry:
    """Dr Inventory, Cr Cash/AP.  Optionally splits HST ITC."""
    inventory_id = _require_account(db, org_id, "1300")
    cash_id = _require_account(db, org_id, pay_with)

    lines: list[dict] = [
        {"account_id": inventory_id, "debit_amount": amount},
        {"account_id": cash_id, "credit_amount": amount},
    ]
    if tax_amount is not None and tax_amount > 0:
        if tax_amount >= amount:
            raise ValidationError("tax_amount must be less than amount")
        itc_id = _require_account(db, org_id, "2150")
        lines[0]["debit_amount"] = amount - tax_amount
        lines.append({"account_id": itc_id, "debit_amount": tax_amount})

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Inventory purchase{f': {vendor}' if vendor else ''}",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )


# ─────────────────────────────────────────────────────────────────
# 7.  declare_dividend  (§1.1)
# ─────────────────────────────────────────────────────────────────


def declare_dividend(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    shareholder: str,
    entry_date: date,
) -> dict:
    """Dr Retained Earnings, Cr Dividends Declared.

    Also generates a board resolution document (§1.1).
    Returns dict with ``journal_entry`` and ``resolution``.
    """
    retained_id = _require_account(db, org_id, "3100")
    dividends_id = _require_account(db, org_id, "3200")

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Dividend declared to {shareholder}",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": retained_id, "debit_amount": amount},
            {"account_id": dividends_id, "credit_amount": amount},
        ],
    )

    resolution = create_corporate_document(
        db,
        org_id=org_id,
        document_type=DocumentType.DIVIDEND_RESOLUTION,
        doc_date=entry_date,
        description=(
            f"Board resolution: dividend of ${amount} to {shareholder}"
        ),
        related_journal_entry_id=je.id,
    )

    return {"journal_entry": je, "resolution": resolution}


# ─────────────────────────────────────────────────────────────────
# 8.  pay_dividend  (§1.1)
# ─────────────────────────────────────────────────────────────────


def pay_dividend(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    shareholder: str,
    entry_date: date,
    pay_with: str = "1000",
) -> dict:
    """Dr Dividends Declared, Cr Cash.

    Also generates a T5 slip document placeholder.
    Returns dict with ``journal_entry`` and ``t5_document``.
    """
    dividends_id = _require_account(db, org_id, "3200")
    cash_id = _require_account(db, org_id, pay_with)

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Dividend paid to {shareholder}",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": dividends_id, "debit_amount": amount},
            {"account_id": cash_id, "credit_amount": amount},
        ],
    )

    t5 = create_corporate_document(
        db,
        org_id=org_id,
        document_type=DocumentType.T5_SLIP,
        doc_date=entry_date,
        description=f"T5 slip: ${amount} dividend to {shareholder} ({entry_date.year})",
        related_journal_entry_id=je.id,
    )

    return {"journal_entry": je, "t5_document": t5}


# ─────────────────────────────────────────────────────────────────
# 9.  capital_injection
# ─────────────────────────────────────────────────────────────────


def capital_injection(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    receive_into: str = "1000",
    description: str | None = None,
) -> JournalEntry:
    """Dr Cash, Cr Share Capital."""
    cash_id = _require_account(db, org_id, receive_into)
    equity_id = _require_account(db, org_id, "3000")

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=description or "Capital injection",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": cash_id, "debit_amount": amount},
            {"account_id": equity_id, "credit_amount": amount},
        ],
    )


# ─────────────────────────────────────────────────────────────────
# 10. shareholder_loan_to_company
# ─────────────────────────────────────────────────────────────────


def shareholder_loan_to_company(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    shareholder: str,
    entry_date: date,
    receive_into: str = "1000",
) -> dict:
    """Shareholder lends money TO the company.

    Dr Cash, Cr Shareholder Loan (liability).
    Records ledger transaction (positive = company owes shareholder).
    """
    cash_id = _require_account(db, org_id, receive_into)
    loan_id = _require_account(db, org_id, "2400")

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Loan from shareholder: {shareholder}",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": cash_id, "debit_amount": amount},
            {"account_id": loan_id, "credit_amount": amount},
        ],
    )

    ledger = create_shareholder_loan_transaction(
        db,
        org_id=org_id,
        shareholder_name=shareholder,
        transaction_date=entry_date,
        amount=amount,
        description=f"Loan to company",
        journal_entry_id=je.id,
    )

    return {"journal_entry": je, "ledger_entry": ledger}


# ─────────────────────────────────────────────────────────────────
# 11. shareholder_loan_from_company
# ─────────────────────────────────────────────────────────────────


def shareholder_loan_from_company(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    shareholder: str,
    entry_date: date,
    pay_with: str = "1000",
) -> dict:
    """Company lends money TO a shareholder (or pays personal expense).

    Dr Shareholder Loan (asset/receivable), Cr Cash.
    Records ledger transaction (negative = shareholder owes company).
    Triggers s.15(2) risk detection.
    """
    loan_id = _require_account(db, org_id, "2400")
    cash_id = _require_account(db, org_id, pay_with)

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"Loan to shareholder: {shareholder}",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": loan_id, "debit_amount": amount},
            {"account_id": cash_id, "credit_amount": amount},
        ],
    )

    ledger = create_shareholder_loan_transaction(
        db,
        org_id=org_id,
        shareholder_name=shareholder,
        transaction_date=entry_date,
        amount=-amount,
        description=f"Loan from company",
        journal_entry_id=je.id,
    )

    return {"journal_entry": je, "ledger_entry": ledger}


# ─────────────────────────────────────────────────────────────────
# 12. record_loan_payment
# ─────────────────────────────────────────────────────────────────


def record_loan_payment(
    db: Session,
    *,
    org_id: uuid.UUID,
    principal_amount: Decimal,
    interest_amount: Decimal,
    entry_date: date,
    pay_with: str = "1000",
    loan_account_number: str = "2500",
    description: str | None = None,
) -> JournalEntry:
    """Dr Loans Payable (principal) + Dr Interest Expense, Cr Cash."""
    loan_id = _require_account(db, org_id, loan_account_number)
    interest_id = _require_account(db, org_id, "6100")
    cash_id = _require_account(db, org_id, pay_with)
    total = principal_amount + interest_amount

    lines: list[dict] = [
        {"account_id": loan_id, "debit_amount": principal_amount},
        {"account_id": interest_id, "debit_amount": interest_amount},
        {"account_id": cash_id, "credit_amount": total},
    ]

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=description or "Loan payment",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )


# ─────────────────────────────────────────────────────────────────
# 13. record_tax_payment
# ─────────────────────────────────────────────────────────────────


def record_tax_payment(
    db: Session,
    *,
    org_id: uuid.UUID,
    amount: Decimal,
    tax_type: TaxType,
    entry_date: date,
    period_start: date,
    period_end: date,
    pay_with: str = "1000",
) -> dict:
    """Dr Tax Payable, Cr Cash.  Also updates/creates the tax obligation."""
    if tax_type in (TaxType.HST, TaxType.GST):
        payable_id = _require_account(db, org_id, "2100")
    else:
        payable_id = _require_account(db, org_id, "2200")

    cash_id = _require_account(db, org_id, pay_with)

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=f"{tax_type.value.upper()} payment for {period_start}–{period_end}",
        source=JournalEntrySource.MANUAL,
        lines=[
            {"account_id": payable_id, "debit_amount": amount},
            {"account_id": cash_id, "credit_amount": amount},
        ],
    )

    obligation = create_tax_obligation(
        db,
        org_id=org_id,
        tax_type=tax_type,
        period_start=period_start,
        period_end=period_end,
        net_owing=amount,
        payment_journal_entry_id=je.id,
    )

    return {"journal_entry": je, "tax_obligation": obligation}


# ─────────────────────────────────────────────────────────────────
# 14. record_asset_disposition
# ─────────────────────────────────────────────────────────────────


def record_asset_disposition(
    db: Session,
    *,
    org_id: uuid.UUID,
    asset_id: uuid.UUID,
    proceeds: Decimal,
    disposition_date: date,
    asset_account_number: str = "1500",
    receive_into: str = "1000",
) -> dict:
    """Dispose of an asset: Dr Cash, Cr Asset.  Gain/loss booked to FX/Other.

    Returns dict with ``journal_entry`` and ``asset``.
    """
    from app.actions.assets import get_asset

    asset = get_asset(db, asset_id)
    cost = asset.acquisition_cost

    asset_acct_id = _require_account(db, org_id, asset_account_number)
    cash_id = _require_account(db, org_id, receive_into)

    lines: list[dict] = [
        {"account_id": cash_id, "debit_amount": proceeds},
        {"account_id": asset_acct_id, "credit_amount": cost},
    ]

    gain_loss = proceeds - cost
    if gain_loss > 0:
        gain_loss_id = _require_account(db, org_id, "6000")
        lines.append({"account_id": gain_loss_id, "credit_amount": gain_loss})
    elif gain_loss < 0:
        gain_loss_id = _require_account(db, org_id, "6000")
        lines.append({"account_id": gain_loss_id, "debit_amount": abs(gain_loss)})

    je = create_journal_entry(
        db,
        org_id=org_id,
        entry_date=disposition_date,
        description=f"Disposition of asset: {asset.name}",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )

    disposed_asset = dispose_asset(
        db,
        asset_id=asset_id,
        disposition_date=disposition_date,
        disposition_proceeds=proceeds,
    )

    return {"journal_entry": je, "asset": disposed_asset}


# ─────────────────────────────────────────────────────────────────
# 15. record_fx_conversion  (§1.6)
# ─────────────────────────────────────────────────────────────────


def record_fx_conversion(
    db: Session,
    *,
    org_id: uuid.UUID,
    from_amount_cad: Decimal,
    to_amount_cad: Decimal,
    entry_date: date,
    from_account: str = "1000",
    to_account: str = "1010",
    description: str | None = None,
) -> JournalEntry:
    """Record an FX conversion between two cash accounts.

    Both amounts are expressed in CAD equivalent.
    Any difference is posted to FX Gains/Losses.
    """
    from_id = _require_account(db, org_id, from_account)
    to_id = _require_account(db, org_id, to_account)
    fx_id = _require_account(db, org_id, "6000")

    lines: list[dict] = [
        {"account_id": to_id, "debit_amount": to_amount_cad},
        {"account_id": from_id, "credit_amount": from_amount_cad},
    ]

    diff = to_amount_cad - from_amount_cad
    if diff > 0:
        lines.append({"account_id": fx_id, "credit_amount": diff})
    elif diff < 0:
        lines.append({"account_id": fx_id, "debit_amount": abs(diff)})

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=entry_date,
        description=description or "FX conversion",
        source=JournalEntrySource.MANUAL,
        lines=lines,
    )


# ─────────────────────────────────────────────────────────────────
# 16. period_end_close  (§1.8)
# ─────────────────────────────────────────────────────────────────


def period_end_close(
    db: Session,
    *,
    org_id: uuid.UUID,
    period_end_date: date,
) -> JournalEntry | None:
    """Close all revenue and expense accounts to Retained Earnings.

    Generates a single closing journal entry.
    Returns None if there is nothing to close (all balances zero).
    """
    from sqlalchemy import func as sqla_func, select as sqla_select

    from app.models.account import ChartOfAccounts
    from app.models.enums import AccountType
    from app.models.journal import JournalEntry as JE, JournalEntryLine

    retained_id = _require_account(db, org_id, "3100")

    # Sum net debit - credit for all revenue/expense accounts
    # that have posted entries.
    stmt = (
        sqla_select(
            ChartOfAccounts.id,
            ChartOfAccounts.account_type,
            (
                sqla_func.coalesce(sqla_func.sum(JournalEntryLine.debit_amount), 0)
                - sqla_func.coalesce(sqla_func.sum(JournalEntryLine.credit_amount), 0)
            ).label("net_balance"),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == ChartOfAccounts.id)
        .join(JE, JE.id == JournalEntryLine.journal_entry_id)
        .where(
            ChartOfAccounts.org_id == org_id,
            ChartOfAccounts.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE]),
            JE.status == JournalEntryStatus.POSTED,
            JE.entry_date <= period_end_date,
        )
        .group_by(ChartOfAccounts.id, ChartOfAccounts.account_type)
    )

    rows = db.execute(stmt).all()
    if not rows:
        return None

    lines: list[dict] = []
    net_to_retained = Decimal("0")

    for account_id, account_type, net_balance in rows:
        net_balance = Decimal(str(net_balance))
        if net_balance == 0:
            continue

        # Revenue accounts normally have credit balances (negative net).
        # Expense accounts normally have debit balances (positive net).
        # To close: reverse the balance.
        if net_balance > 0:
            lines.append({"account_id": account_id, "credit_amount": net_balance})
            net_to_retained += net_balance
        else:
            lines.append({"account_id": account_id, "debit_amount": abs(net_balance)})
            net_to_retained -= abs(net_balance)

    if not lines:
        return None

    # Plug to Retained Earnings
    if net_to_retained > 0:
        lines.append({"account_id": retained_id, "debit_amount": net_to_retained})
    elif net_to_retained < 0:
        lines.append({"account_id": retained_id, "credit_amount": abs(net_to_retained)})

    return create_journal_entry(
        db,
        org_id=org_id,
        entry_date=period_end_date,
        description=f"Period-end closing entry ({period_end_date})",
        source=JournalEntrySource.SYSTEM,
        status=JournalEntryStatus.DRAFT,
        lines=lines,
    )
