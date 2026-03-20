"""API routes for rule-engine template functions (§1.1).

Each endpoint corresponds to a high-level business event / intent
and delegates to the matching action in ``app.actions.rule_templates``.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.actions import rule_templates as tpl
from app.database import get_db
from app.models.enums import TaxType

router = APIRouter(prefix="/templates", tags=["templates"])


# ── Shared helpers ───────────────────────────────────────────────


class _JournalEntryRef(BaseModel):
    id: uuid.UUID
    description: str | None

    model_config = {"from_attributes": True}


# ── 1. Operating Expense ─────────────────────────────────────────


class OperatingExpenseIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    expense_category: str
    entry_date: date
    vendor: str | None = None
    tax_amount: Decimal | None = None
    pay_with: str = "1000"


@router.post("/operating-expense", status_code=201)
def operating_expense(payload: OperatingExpenseIn, db: Session = Depends(get_db)):
    je = tpl.record_operating_expense(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 2. Capital Expenditure ───────────────────────────────────────


class CapitalExpenditureIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    asset_name: str
    entry_date: date
    cca_class: str
    asset_account_number: str = "1500"
    pay_with: str = "1000"
    tax_amount: Decimal | None = None
    description: str | None = None


@router.post("/capital-expenditure", status_code=201)
def capital_expenditure(payload: CapitalExpenditureIn, db: Session = Depends(get_db)):
    result = tpl.record_capital_expenditure(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "asset_id": str(result["asset"].id),
        "cca_claimed": str(result["cca_entry"].cca_claimed),
    }


# ── 3. Revenue (one-time) ───────────────────────────────────────


class RevenueOnetimeIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    entry_date: date
    description: str | None = None
    revenue_account_number: str = "4000"
    receive_into: str = "1000"
    tax_collected: Decimal | None = None


@router.post("/revenue-onetime", status_code=201)
def revenue_onetime(payload: RevenueOnetimeIn, db: Session = Depends(get_db)):
    je = tpl.record_revenue_onetime(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 4. Subscription Revenue ──────────────────────────────────────


class SubscriptionRevenueIn(BaseModel):
    org_id: uuid.UUID
    total_amount: Decimal
    start_date: date
    end_date: date
    description: str | None = None
    receive_into: str = "1000"
    revenue_account_number: str = "4000"


@router.post("/subscription-revenue", status_code=201)
def subscription_revenue(payload: SubscriptionRevenueIn, db: Session = Depends(get_db)):
    result = tpl.record_subscription_revenue(db, **payload.model_dump())
    db.commit()
    return {
        "receipt_entry": _JournalEntryRef.model_validate(result["receipt_entry"]),
        "scheduled_entry_id": str(result["scheduled_entry"].id),
    }


# ── 5. Refund ────────────────────────────────────────────────────


class RefundIn(BaseModel):
    org_id: uuid.UUID
    original_journal_entry_id: uuid.UUID
    refund_date: date
    created_by: str | None = None


@router.post("/refund", status_code=201)
def refund(payload: RefundIn, db: Session = Depends(get_db)):
    je = tpl.record_refund(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 6. Inventory Purchase ────────────────────────────────────────


class InventoryPurchaseIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    entry_date: date
    vendor: str | None = None
    pay_with: str = "1000"
    tax_amount: Decimal | None = None


@router.post("/inventory-purchase", status_code=201)
def inventory_purchase(payload: InventoryPurchaseIn, db: Session = Depends(get_db)):
    je = tpl.record_inventory_purchase(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 7. Declare Dividend ──────────────────────────────────────────


class DeclareDividendIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    shareholder: str
    entry_date: date


@router.post("/declare-dividend", status_code=201)
def declare_dividend(payload: DeclareDividendIn, db: Session = Depends(get_db)):
    result = tpl.declare_dividend(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "resolution_id": str(result["resolution"].id),
    }


# ── 8. Pay Dividend ──────────────────────────────────────────────


class PayDividendIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    shareholder: str
    entry_date: date
    pay_with: str = "1000"


@router.post("/pay-dividend", status_code=201)
def pay_dividend(payload: PayDividendIn, db: Session = Depends(get_db)):
    result = tpl.pay_dividend(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "t5_document_id": str(result["t5_document"].id),
    }


# ── 9. Capital Injection ─────────────────────────────────────────


class CapitalInjectionIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    entry_date: date
    receive_into: str = "1000"
    description: str | None = None


@router.post("/capital-injection", status_code=201)
def capital_injection_route(payload: CapitalInjectionIn, db: Session = Depends(get_db)):
    je = tpl.capital_injection(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 10. Shareholder Loan TO Company ──────────────────────────────


class ShareholderLoanToCompanyIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    shareholder: str
    entry_date: date
    receive_into: str = "1000"


@router.post("/shareholder-loan-to-company", status_code=201)
def sh_loan_to_company(payload: ShareholderLoanToCompanyIn, db: Session = Depends(get_db)):
    result = tpl.shareholder_loan_to_company(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "running_balance": str(result["ledger_entry"].running_balance),
    }


# ── 11. Shareholder Loan FROM Company ────────────────────────────


class ShareholderLoanFromCompanyIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    shareholder: str
    entry_date: date
    pay_with: str = "1000"


@router.post("/shareholder-loan-from-company", status_code=201)
def sh_loan_from_company(payload: ShareholderLoanFromCompanyIn, db: Session = Depends(get_db)):
    result = tpl.shareholder_loan_from_company(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "running_balance": str(result["ledger_entry"].running_balance),
    }


# ── 12. Loan Payment ─────────────────────────────────────────────


class LoanPaymentIn(BaseModel):
    org_id: uuid.UUID
    principal_amount: Decimal
    interest_amount: Decimal
    entry_date: date
    pay_with: str = "1000"
    loan_account_number: str = "2500"
    description: str | None = None


@router.post("/loan-payment", status_code=201)
def loan_payment(payload: LoanPaymentIn, db: Session = Depends(get_db)):
    je = tpl.record_loan_payment(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 13. Tax Payment ──────────────────────────────────────────────


class TaxPaymentIn(BaseModel):
    org_id: uuid.UUID
    amount: Decimal
    tax_type: TaxType
    entry_date: date
    period_start: date
    period_end: date
    pay_with: str = "1000"


@router.post("/tax-payment", status_code=201)
def tax_payment(payload: TaxPaymentIn, db: Session = Depends(get_db)):
    result = tpl.record_tax_payment(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "tax_obligation_id": str(result["tax_obligation"].id),
    }


# ── 14. Asset Disposition ────────────────────────────────────────


class AssetDispositionIn(BaseModel):
    org_id: uuid.UUID
    asset_id: uuid.UUID
    proceeds: Decimal
    disposition_date: date
    asset_account_number: str = "1500"
    receive_into: str = "1000"


@router.post("/asset-disposition", status_code=201)
def asset_disposition(payload: AssetDispositionIn, db: Session = Depends(get_db)):
    result = tpl.record_asset_disposition(db, **payload.model_dump())
    db.commit()
    return {
        "journal_entry": _JournalEntryRef.model_validate(result["journal_entry"]),
        "asset_id": str(result["asset"].id),
        "asset_status": result["asset"].status.value,
    }


# ── 15. FX Conversion ────────────────────────────────────────────


class FXConversionIn(BaseModel):
    org_id: uuid.UUID
    from_amount_cad: Decimal
    to_amount_cad: Decimal
    entry_date: date
    from_account: str = "1000"
    to_account: str = "1010"
    description: str | None = None


@router.post("/fx-conversion", status_code=201)
def fx_conversion(payload: FXConversionIn, db: Session = Depends(get_db)):
    je = tpl.record_fx_conversion(db, **payload.model_dump())
    db.commit()
    db.refresh(je)
    return _JournalEntryRef.model_validate(je)


# ── 16. Period-End Close ─────────────────────────────────────────


class PeriodEndCloseIn(BaseModel):
    org_id: uuid.UUID
    period_end_date: date


@router.post("/period-end-close", status_code=201)
def period_end_close(payload: PeriodEndCloseIn, db: Session = Depends(get_db)):
    je = tpl.period_end_close(db, **payload.model_dump())
    db.commit()
    if je is None:
        return {"message": "nothing to close", "journal_entry": None}
    db.refresh(je)
    return {"journal_entry": _JournalEntryRef.model_validate(je)}
