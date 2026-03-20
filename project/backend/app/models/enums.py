from enum import Enum


# ── Chart of Accounts ────────────────────────────────────────────

class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class AccountSubType(str, Enum):
    # Assets
    CURRENT_ASSET = "current_asset"
    FIXED_ASSET = "fixed_asset"
    CCA_ASSET = "cca_asset"
    # Liabilities
    CURRENT_LIABILITY = "current_liability"
    LONG_TERM_LIABILITY = "long_term_liability"
    # Equity
    SHARE_CAPITAL = "share_capital"
    RETAINED_EARNINGS = "retained_earnings"
    DIVIDENDS = "dividends"
    # Revenue
    SALES_REVENUE = "sales_revenue"
    SERVICE_REVENUE = "service_revenue"
    # Expense
    OPERATING_EXPENSE = "operating_expense"
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    CCA_EXPENSE = "cca_expense"
    # Other
    OTHER_INCOME = "other_income"
    OTHER_EXPENSE = "other_expense"


class AccountCreator(str, Enum):
    USER = "user"
    SYSTEM = "system"


# ── Journal Entries ──────────────────────────────────────────────

class JournalEntryStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    POSTED = "posted"
    REVERSED = "reversed"


class JournalEntrySource(str, Enum):
    MANUAL = "manual"
    STRIPE = "stripe"
    WISE = "wise"
    PLAID = "plaid"
    SYSTEM = "system"


# ── Assets ───────────────────────────────────────────────────────

class AssetStatus(str, Enum):
    ACTIVE = "active"
    DISPOSED = "disposed"


# ── Tax ──────────────────────────────────────────────────────────

class TaxType(str, Enum):
    HST = "hst"
    GST = "gst"
    PST = "pst"
    CORPORATE_INCOME = "corporate_income"


class TaxObligationStatus(str, Enum):
    ACCRUING = "accruing"
    CALCULATED = "calculated"
    FILED = "filed"
    PAID = "paid"


# ── Corporate Documents ─────────────────────────────────────────

class DocumentType(str, Enum):
    DIVIDEND_RESOLUTION = "dividend_resolution"
    DIRECTORS_RESOLUTION = "directors_resolution"
    ANNUAL_RETURN = "annual_return"
    ARTICLES_OF_AMENDMENT = "articles_of_amendment"
    T5_SLIP = "t5_slip"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    SIGNED = "signed"


# ── Scheduled Entries ────────────────────────────────────────────

class ScheduleFrequency(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ScheduleSource(str, Enum):
    CCA = "cca"
    PRORATION = "proration"
    DEFERRED_REVENUE = "deferred_revenue"
    RECURRING = "recurring"


class ScheduleStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


# ── Integrations ─────────────────────────────────────────────────

class IntegrationPlatform(str, Enum):
    STRIPE = "stripe"
    WISE = "wise"
    PLAID = "plaid"
    SHOPIFY = "shopify"
    LEMONSQUEEZY = "lemonsqueezy"
    PADDLE = "paddle"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


# ── Reconciliation ──────────────────────────────────────────────

class ReconciliationStatus(str, Enum):
    AUTO_MATCHED = "auto_matched"
    USER_CONFIRMED = "user_confirmed"
    MANUAL = "manual"
    DISCREPANCY = "discrepancy"
