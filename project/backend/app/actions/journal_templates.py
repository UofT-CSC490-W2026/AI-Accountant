"""
Journal Entry Templates

Pre-defined templates for common accounting transactions:
- Operating expenses
- Capital expenditures
- Revenue recognition
- Dividends
- Shareholder loans
- Tax payments
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.journal import JournalEntry
from app.models.enums import JournalEntrySource
from app.services.accounting_engine import JournalLineInput, create_journal_entry
from app.services.coa_manager import get_account_by_number


def record_operating_expense(
    db: Session,
    org_id: uuid.UUID,
    expense_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    vendor: str,
    tax_amount: Decimal | None = None,
    hst_receivable_account_id: uuid.UUID | None = None,
    description: str | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record an operating expense.

    Dr. Expense Account     (amount - tax)
    Dr. HST Receivable      (tax, if applicable)
        Cr. Cash/AP         (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        expense_account_id: The expense account to debit.
        cash_account_id: The cash/AP account to credit.
        amount: Total amount paid (including tax).
        entry_date: Date of the expense.
        vendor: Vendor name.
        tax_amount: HST/GST amount (ITC).
        hst_receivable_account_id: HST receivable account (required if tax_amount).
        description: Optional description.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = []

    if tax_amount and tax_amount > 0:
        if hst_receivable_account_id is None:
            raise ValueError("hst_receivable_account_id required when tax_amount is provided")

        net_amount = amount - tax_amount
        lines.append(JournalLineInput(
            account_id=expense_account_id,
            debit=net_amount,
            description=f"{vendor} - expense",
        ))
        lines.append(JournalLineInput(
            account_id=hst_receivable_account_id,
            debit=tax_amount,
            description=f"{vendor} - HST ITC",
        ))
    else:
        lines.append(JournalLineInput(
            account_id=expense_account_id,
            debit=amount,
            description=f"{vendor}",
        ))

    lines.append(JournalLineInput(
        account_id=cash_account_id,
        credit=amount,
    ))

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=description or f"Expense: {vendor}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_capital_expenditure(
    db: Session,
    org_id: uuid.UUID,
    asset_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    asset_name: str,
    tax_amount: Decimal | None = None,
    hst_receivable_account_id: uuid.UUID | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a capital expenditure (asset purchase).

    Dr. Asset Account       (amount - tax)
    Dr. HST Receivable      (tax, if applicable)
        Cr. Cash/AP         (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        asset_account_id: The asset account to debit.
        cash_account_id: The cash/AP account to credit.
        amount: Total amount paid (including tax).
        entry_date: Date of purchase.
        asset_name: Name/description of the asset.
        tax_amount: HST/GST amount (ITC).
        hst_receivable_account_id: HST receivable account.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = []

    if tax_amount and tax_amount > 0:
        if hst_receivable_account_id is None:
            raise ValueError("hst_receivable_account_id required when tax_amount is provided")

        net_amount = amount - tax_amount
        lines.append(JournalLineInput(
            account_id=asset_account_id,
            debit=net_amount,
            description=asset_name,
        ))
        lines.append(JournalLineInput(
            account_id=hst_receivable_account_id,
            debit=tax_amount,
            description=f"{asset_name} - HST ITC",
        ))
    else:
        lines.append(JournalLineInput(
            account_id=asset_account_id,
            debit=amount,
            description=asset_name,
        ))

    lines.append(JournalLineInput(
        account_id=cash_account_id,
        credit=amount,
    ))

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=f"Capital expenditure: {asset_name}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_revenue(
    db: Session,
    org_id: uuid.UUID,
    revenue_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    customer: str | None = None,
    tax_amount: Decimal | None = None,
    hst_payable_account_id: uuid.UUID | None = None,
    description: str | None = None,
    source: JournalEntrySource = JournalEntrySource.MANUAL,
    source_reference_id: str | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record revenue received.

    Dr. Cash/AR             (amount)
        Cr. Revenue         (amount - tax)
        Cr. HST Payable     (tax, if applicable)

    Args:
        db: Database session.
        org_id: Organization ID.
        revenue_account_id: The revenue account to credit.
        cash_account_id: The cash/AR account to debit.
        amount: Total amount received (including tax).
        entry_date: Date of the transaction.
        customer: Customer name.
        tax_amount: HST/GST collected.
        hst_payable_account_id: HST payable account.
        description: Optional description.
        source: Source of the entry.
        source_reference_id: External reference ID.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=cash_account_id,
            debit=amount,
            description=customer,
        )
    ]

    if tax_amount and tax_amount > 0:
        if hst_payable_account_id is None:
            raise ValueError("hst_payable_account_id required when tax_amount is provided")

        net_amount = amount - tax_amount
        lines.append(JournalLineInput(
            account_id=revenue_account_id,
            credit=net_amount,
            description=customer,
        ))
        lines.append(JournalLineInput(
            account_id=hst_payable_account_id,
            credit=tax_amount,
            description=f"HST collected",
        ))
    else:
        lines.append(JournalLineInput(
            account_id=revenue_account_id,
            credit=amount,
            description=customer,
        ))

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=description or f"Revenue: {customer or 'Sale'}",
        source=source,
        source_reference_id=source_reference_id,
        auto_post=auto_post,
    )


def record_refund(
    db: Session,
    org_id: uuid.UUID,
    revenue_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    customer: str | None = None,
    tax_amount: Decimal | None = None,
    hst_payable_account_id: uuid.UUID | None = None,
    original_entry_id: uuid.UUID | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a refund (reversal of revenue).

    Dr. Revenue             (amount - tax)
    Dr. HST Payable         (tax, if applicable)
        Cr. Cash/AR         (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        revenue_account_id: The revenue account to debit.
        cash_account_id: The cash/AR account to credit.
        amount: Total refund amount (including tax).
        entry_date: Date of the refund.
        customer: Customer name.
        tax_amount: HST/GST to reverse.
        hst_payable_account_id: HST payable account.
        original_entry_id: ID of the original revenue entry.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = []

    if tax_amount and tax_amount > 0:
        if hst_payable_account_id is None:
            raise ValueError("hst_payable_account_id required when tax_amount is provided")

        net_amount = amount - tax_amount
        lines.append(JournalLineInput(
            account_id=revenue_account_id,
            debit=net_amount,
            description=f"Refund: {customer}",
        ))
        lines.append(JournalLineInput(
            account_id=hst_payable_account_id,
            debit=tax_amount,
            description="HST refund adjustment",
        ))
    else:
        lines.append(JournalLineInput(
            account_id=revenue_account_id,
            debit=amount,
            description=f"Refund: {customer}",
        ))

    lines.append(JournalLineInput(
        account_id=cash_account_id,
        credit=amount,
    ))

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=f"Refund: {customer or 'Customer'}",
        source=JournalEntrySource.MANUAL,
        source_reference_id=str(original_entry_id) if original_entry_id else None,
        auto_post=auto_post,
    )


def declare_dividend(
    db: Session,
    org_id: uuid.UUID,
    retained_earnings_account_id: uuid.UUID,
    dividends_payable_account_id: uuid.UUID,
    amount: Decimal,
    declaration_date: date,
    shareholder: str,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a dividend declaration.

    Dr. Retained Earnings   (amount)
        Cr. Dividends Payable   (amount)

    Note: This should be accompanied by a board resolution document.

    Args:
        db: Database session.
        org_id: Organization ID.
        retained_earnings_account_id: Retained earnings account.
        dividends_payable_account_id: Dividends payable account.
        amount: Dividend amount.
        declaration_date: Date of declaration.
        shareholder: Shareholder name.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=retained_earnings_account_id,
            debit=amount,
            description=f"Dividend declared to {shareholder}",
        ),
        JournalLineInput(
            account_id=dividends_payable_account_id,
            credit=amount,
            description=f"Dividend payable to {shareholder}",
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=declaration_date,
        lines=lines,
        description=f"Dividend declaration: {shareholder} - ${amount}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def pay_dividend(
    db: Session,
    org_id: uuid.UUID,
    dividends_payable_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    payment_date: date,
    shareholder: str,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a dividend payment.

    Dr. Dividends Payable   (amount)
        Cr. Cash            (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        dividends_payable_account_id: Dividends payable account.
        cash_account_id: Cash account.
        amount: Payment amount.
        payment_date: Date of payment.
        shareholder: Shareholder name.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=dividends_payable_account_id,
            debit=amount,
            description=f"Dividend paid to {shareholder}",
        ),
        JournalLineInput(
            account_id=cash_account_id,
            credit=amount,
            description=f"Dividend payment: {shareholder}",
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=payment_date,
        lines=lines,
        description=f"Dividend payment: {shareholder} - ${amount}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_capital_injection(
    db: Session,
    org_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    share_capital_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    shareholder: str,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a capital injection (owner investment).

    Dr. Cash                (amount)
        Cr. Share Capital   (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        cash_account_id: Cash account.
        share_capital_account_id: Share capital account.
        amount: Investment amount.
        entry_date: Date of investment.
        shareholder: Shareholder name.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=cash_account_id,
            debit=amount,
            description=f"Capital injection from {shareholder}",
        ),
        JournalLineInput(
            account_id=share_capital_account_id,
            credit=amount,
            description=f"Share capital: {shareholder}",
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=f"Capital injection: {shareholder} - ${amount}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_shareholder_loan_to_company(
    db: Session,
    org_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    shareholder_loan_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    shareholder: str,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a shareholder loan to the company.

    Dr. Cash                    (amount)
        Cr. Shareholder Loan    (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        cash_account_id: Cash account.
        shareholder_loan_account_id: Shareholder loan account.
        amount: Loan amount.
        entry_date: Date of loan.
        shareholder: Shareholder name.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=cash_account_id,
            debit=amount,
            description=f"Loan from {shareholder}",
        ),
        JournalLineInput(
            account_id=shareholder_loan_account_id,
            credit=amount,
            description=f"Shareholder loan: {shareholder}",
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=f"Shareholder loan to company: {shareholder} - ${amount}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_shareholder_loan_from_company(
    db: Session,
    org_id: uuid.UUID,
    shareholder_loan_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    shareholder: str,
    description: str | None = None,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record a loan from the company to a shareholder (or personal expense paid by company).

    Dr. Shareholder Loan    (amount)
        Cr. Cash            (amount)

    Note: This creates a receivable from the shareholder. Watch for s.15(2) implications.

    Args:
        db: Database session.
        org_id: Organization ID.
        shareholder_loan_account_id: Shareholder loan account.
        cash_account_id: Cash account.
        amount: Amount.
        entry_date: Date.
        shareholder: Shareholder name.
        description: Optional description.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=shareholder_loan_account_id,
            debit=amount,
            description=description or f"Due from {shareholder}",
        ),
        JournalLineInput(
            account_id=cash_account_id,
            credit=amount,
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=description or f"Shareholder loan from company: {shareholder} - ${amount}",
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )


def record_cca_expense(
    db: Session,
    org_id: uuid.UUID,
    cca_expense_account_id: uuid.UUID,
    accumulated_depreciation_account_id: uuid.UUID,
    amount: Decimal,
    entry_date: date,
    fiscal_year: int,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record CCA (depreciation) expense.

    Dr. CCA Expense                 (amount)
        Cr. Accumulated Depreciation    (amount)

    Args:
        db: Database session.
        org_id: Organization ID.
        cca_expense_account_id: CCA expense account.
        accumulated_depreciation_account_id: Accumulated depreciation account.
        amount: CCA amount.
        entry_date: Date (typically fiscal year-end).
        fiscal_year: The fiscal year.
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    lines = [
        JournalLineInput(
            account_id=cca_expense_account_id,
            debit=amount,
            description=f"CCA for fiscal year {fiscal_year}",
        ),
        JournalLineInput(
            account_id=accumulated_depreciation_account_id,
            credit=amount,
            description=f"Accumulated depreciation {fiscal_year}",
        ),
    ]

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=f"CCA expense for fiscal year {fiscal_year}",
        source=JournalEntrySource.SYSTEM,
        auto_post=auto_post,
    )


def record_hst_payment(
    db: Session,
    org_id: uuid.UUID,
    hst_payable_account_id: uuid.UUID,
    hst_receivable_account_id: uuid.UUID,
    cash_account_id: uuid.UUID,
    tax_collected: Decimal,
    itcs: Decimal,
    entry_date: date,
    period_description: str,
    auto_post: bool = False,
) -> JournalEntry:
    """
    Record HST remittance payment (or refund receipt).

    If net owing (tax_collected > itcs):
        Dr. HST Payable         (tax_collected)
            Cr. HST Receivable  (itcs)
            Cr. Cash            (net_owing)

    If net refund (itcs > tax_collected):
        Dr. HST Payable         (tax_collected)
        Dr. Cash                (net_refund)
            Cr. HST Receivable  (itcs)

    Args:
        db: Database session.
        org_id: Organization ID.
        hst_payable_account_id: HST payable account.
        hst_receivable_account_id: HST receivable (ITCs) account.
        cash_account_id: Cash account.
        tax_collected: Total HST collected in the period.
        itcs: Total ITCs claimed in the period.
        entry_date: Date of payment/receipt.
        period_description: Description of the period (e.g., "Q1 2024").
        auto_post: If True, immediately post the entry.

    Returns:
        The created JournalEntry.
    """
    net = tax_collected - itcs
    lines = []

    lines.append(JournalLineInput(
        account_id=hst_payable_account_id,
        debit=tax_collected,
        description=f"HST collected - {period_description}",
    ))

    lines.append(JournalLineInput(
        account_id=hst_receivable_account_id,
        credit=itcs,
        description=f"ITCs claimed - {period_description}",
    ))

    if net > 0:
        lines.append(JournalLineInput(
            account_id=cash_account_id,
            credit=net,
            description=f"HST remittance - {period_description}",
        ))
        description = f"HST remittance: {period_description} - ${net}"
    else:
        lines.append(JournalLineInput(
            account_id=cash_account_id,
            debit=abs(net),
            description=f"HST refund - {period_description}",
        ))
        description = f"HST refund: {period_description} - ${abs(net)}"

    return create_journal_entry(
        db=db,
        org_id=org_id,
        entry_date=entry_date,
        lines=lines,
        description=description,
        source=JournalEntrySource.MANUAL,
        auto_post=auto_post,
    )
