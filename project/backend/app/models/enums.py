import enum


# ── Chart of Accounts ──────────────────────────────────────────────

class AccountType(str, enum.Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class AccountSubType(str, enum.Enum):
    # Assets
    CURRENT_ASSET = "current_asset"
    FIXED_ASSET = "fixed_asset"
    CCA_ASSET = "cca_asset"
    # Liabilities
    CURRENT_LIABILITY = "current_liability"
    LONG_TERM_LIABILITY = "long_term_liability"
    # Equity
    EQUITY = "equity"
    # Revenue
    REVENUE = "revenue"
    # Expenses
    OPERATING_EXPENSE = "operating_expense"
    COST_OF_GOODS_SOLD = "cost_of_goods_sold"
    # Other
    OTHER_INCOME = "other_income"
    OTHER_EXPENSE = "other_expense"


class AccountCreator(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"


# ── Journal Entries ────────────────────────────────────────────────

class JournalEntrySource(str, enum.Enum):
    MANUAL = "manual"
    STRIPE = "stripe"
    WISE = "wise"
    PLAID = "plaid"
    SYSTEM = "system"


class JournalEntryStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    POSTED = "posted"
    REVERSED = "reversed"


# ── Assets / CCA ──────────────────────────────────────────────────

class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    DISPOSED = "disposed"


# ── Tax ───────────────────────────────────────────────────────────

class TaxType(str, enum.Enum):
    HST = "hst"
    CORPORATE_INCOME = "corporate_income"


class TaxObligationStatus(str, enum.Enum):
    ACCRUING = "accruing"
    CALCULATED = "calculated"
    FILED = "filed"
    PAID = "paid"


# ── Corporate Documents ───────────────────────────────────────────

class DocumentType(str, enum.Enum):
    DIVIDEND_RESOLUTION = "dividend_resolution"


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    SIGNED = "signed"


# ── Scheduled Entries ─────────────────────────────────────────────

class ScheduleFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ScheduleSource(str, enum.Enum):
    CCA = "cca"
    PRORATION = "proration"


class ScheduleStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


# ── Integrations ──────────────────────────────────────────────────

class IntegrationPlatform(str, enum.Enum):
    STRIPE = "stripe"
    WISE = "wise"
    PLAID = "plaid"


class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


# ── Reconciliation ────────────────────────────────────────────────

class ReconciliationStatus(str, enum.Enum):
    AUTO_MATCHED = "auto_matched"
    USER_CONFIRMED = "user_confirmed"
    MANUAL = "manual"
