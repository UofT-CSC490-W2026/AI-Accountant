# AI CFO Agent — Project Execution Plan

## Vision

An autonomous AI-powered accounting and corporate administration platform for Canadian small businesses. The system understands natural language business events, automatically produces correct double-entry journal entries, manages corporate governance documents, and proactively advises founders on tax-optimal strategies — so they can focus on building their business instead of fighting their books.

---

## Target User

Solo founders and small teams (2-5 people) running a Canadian corporation, typically:

- $0–$500K revenue
- Using Stripe/Shopify for payments, Wise or a traditional bank for cash
- Cannot afford (or are overpaying for) bookkeepers/CPAs
- Missing tax deductions (CCA, ITCs) they don't know about
- Struggling with corporate compliance (minute books, resolutions, remittances)

---

## Architecture Overview

```
USER INPUT (NL)     BANK FEED          WEBHOOKS (Stripe, etc.)
      │                  │                       │
      ▼                  ▼                       ▼
┌───────────┐    ┌──────────────┐         ┌───────────┐
│ Layer 1   │    │ Layer 1      │         │ Layer 0   │
│ NLU:      │    │ Transaction  │         │ Adapters  │
│ SpaCy +   │    │ Classifier   │         │ (pure     │
│ DeBERTa   │    │ (DeBERTa-sm) │         │  code)    │
│ (intent + │    └──────┬───────┘         └─────┬─────┘
│  entities)│           │                       │
└─────┬─────┘           │                       │
      │                 │                       │
      ▼                 ▼                       ▼
┌──────────────────────────────────────────────────────┐
│ Layer 2: Classification                              │
│ • CoA Manager (auto-create accounts as needed)       │
│ • CCA Class Matcher (MiniLM-L6 similarity)           │
│ • Rule-based account mapping (intent × entity → GL)  │
│ • Confidence gating (auto-proceed vs. ask user)      │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ Layer 3: Rule Engine (deterministic, zero AI)        │
│ • Double-entry journal entry generation              │
│ • CCA calculation (half-year rule, AIIP, classes)    │
│ • Proration / deferred revenue scheduling            │
│ • HST/GST tracking (collected vs. ITCs)              │
│ • Shareholder loan ledger                            │
│ • Dividend workflow (entries + resolution)           │
│ • Reconciliation engine (payout ↔ invoices)          │
│ • FX gain/loss calculation                           │
│ • Period-end close                                   │
└──────────────────────┬───────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ Layer 4: Output Generation                           │
│ • Financial statements (B/S, P&L, trial balance)     │
│ • Corporate resolutions (templates + variable fill)  │
│ • CCA schedule reports                               │
│ • HST/GST summary for filing                         │
└──────────────────────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│ Layer 5: CFO Advisor (LLM, async, periodic)          │
│ • Proactive tax optimization suggestions             │
│ • Anomaly detection ("your expenses spiked 3x")      │
│ • Year-end planning nudges                           │
│ • Plain-English explanations of what the system did  │
└──────────────────────────────────────────────────────┘
```

---

## SLC Feature Scope (v1)

### In Scope

| Category | Features |
|----------|----------|
| **Purchases / Outflows** | Operating expenses (accrual, proration, bank fees); Capital expenditures (CCA scheduling, half-year rule, asset register, disposition); Inventory/COGS (basic, for Shopify users) |
| **Income / Inflows** | One-time revenue (accrual, payment platform fees, sales tax tracking for processor model); Subscription revenue (deferred revenue + monthly proration); Refunds (reversal entries); MoR model support (LemonSqueezy/Paddle — no tax liability on your books) |
| **Finance & Corporate** | Owner's equity / capital injection; Dividend declaration & payment (journal entries + board resolution document); Shareholder loan tracking (both directions, s.15(2) warning); Loan/debt tracking (principal + interest) |
| **Tax & Compliance** | HST/GST tracking (collected - ITCs = net owing); Corporate income tax liability tracking; CCA schedules (tax-basis; optional book-basis) |
| **Period-End** | Year-end closing entries; Adjusting entries; Financial statement generation (Balance Sheet, Income Statement, Trial Balance) |
| **Cross-Cutting** | Multi-currency / FX gains & losses; Bank fee auto-detection; Reconciliation (payment platform ↔ bank); Auto-creation of GL accounts as needed |
| **Integrations** | Stripe, Wise (direct API), Plaid/Flinks (traditional banks); Fast follow: Shopify, LemonSqueezy/Paddle |

### Out of Scope (v1)

- Payroll processing (integrate with a payroll provider instead)
- Section 85 rollovers
- Stock option structuring (s.7 / 110(1)(d.1))
- Inter-corporate dividends (holdco structures)
- Automated CRA filing (track & calculate, but don't file)
- US tax / GAAP (Canadian ASPE only for v1)

---

## Tech Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Backend API** | Python + FastAPI | ML ecosystem is Python-native; FastAPI is async, fast, well-typed |
| **Database** | PostgreSQL | ACID compliance is non-negotiable for financial data; JSONB for flexible metadata |
| **Task Queue** | Celery + Redis | Async processing for webhooks, scheduled CCA entries, proration jobs, LLM advisory calls |
| **ML Inference** | HuggingFace Transformers + SpaCy | DeBERTa fine-tuning, SpaCy for NER pipeline |
| **ML Training** | HuggingFace Trainer + Weights & Biases | Standard fine-tuning pipeline with experiment tracking |
| **Embedding Search** | Sentence-Transformers + pgvector | CCA class matching via semantic similarity, stored in Postgres |
| **LLM (Layer 5)** | Claude API (Sonnet) | Advisory layer only; infrequent, async calls |
| **Document Gen** | Jinja2 templates + python-docx | Corporate resolutions, financial statement PDFs |
| **Frontend** | React + TypeScript | Conversational UI + dashboard |
| **Hosting** | Railway / Fly.io (start), AWS (scale) | Simple deployment for early stage; migrate when needed |

---

## Phase 0: Foundation (Weeks 1–3)

**Goal:** Core data model and double-entry accounting engine — the bedrock everything else builds on.

### 0.1 — Database Schema Design

Design the core tables. Key entities:

```
organizations
├── id, name, incorporation_date, fiscal_year_end
├── jurisdiction (federal/provincial)
└── hst_registration_number, business_number

chart_of_accounts
├── id, org_id, account_number, name
├── account_type (asset | liability | equity | revenue | expense)
├── sub_type (current_asset | fixed_asset | cca_asset | ...)
├── parent_account_id (for hierarchy)
├── currency, is_active
└── created_by (system | user), auto_created (bool)

journal_entries
├── id, org_id, entry_date, posted_date
├── description, source (manual | stripe | wise | plaid | system)
├── source_reference_id (webhook event ID, etc.)
├── status (draft | pending_review | posted | reversed)
└── created_by, approved_by

journal_entry_lines
├── id, journal_entry_id, account_id
├── debit_amount, credit_amount, currency
├── description
└── line_order

assets (for CCA tracking)
├── id, org_id, name, description
├── acquisition_date, acquisition_cost
├── cca_class, cca_rate
├── disposition_date, disposition_proceeds (nullable)
├── book_depreciation_method, book_useful_life (nullable)
└── status (active | disposed)

cca_schedule_entries
├── id, asset_id, fiscal_year
├── ucc_opening, additions, dispositions
├── cca_claimed, ucc_closing
├── half_year_rule_applied (bool)
├── aiip_applied (bool)
└── journal_entry_id (link to the actual entry)

shareholder_loan_ledger
├── id, org_id, shareholder_name
├── transaction_date, amount (+ company owes shareholder, - shareholder owes company)
├── description, journal_entry_id
└── running_balance

tax_obligations
├── id, org_id, tax_type (hst | corporate_income)
├── period_start, period_end
├── amount_collected, itcs_claimed, net_owing
├── status (accruing | calculated | filed | paid)
└── payment_journal_entry_id

corporate_documents
├── id, org_id, document_type (dividend_resolution | ...)
├── date, description
├── generated_file_path
├── related_journal_entry_id
└── status (draft | signed)

scheduled_entries
├── id, org_id, template_journal_entry
├── frequency (monthly | quarterly | yearly)
├── start_date, end_date
├── next_run_date
├── source (cca | proration | ...)
└── status (active | paused | completed)

integration_connections
├── id, org_id, platform (stripe | wise | plaid)
├── credentials (encrypted), status
├── last_sync, webhook_secret
└── config (JSON — account mappings, etc.)

reconciliation_records
├── id, org_id
├── bank_transaction_id, platform_transaction_ids (array)
├── status (auto_matched | user_confirmed | manual)
├── matched_amount, discrepancy_amount
└── journal_entry_id
```

### 0.2 — Double-Entry Accounting Engine

Build the core module that enforces accounting integrity:

- **Every journal entry must balance** — sum of debits = sum of credits (enforce at DB constraint level AND application level)
- **Immutability** — posted entries are never modified; corrections are made via reversing entries
- **Multi-currency support** — store both original currency amount and functional currency (CAD) equivalent
- **Draft → Review → Posted workflow** — entries from integrations can auto-post (high confidence) or go to review queue

### 0.3 — Chart of Accounts Template

Create a standard Canadian small business CoA template:

```
1000–1999  Assets
  1000  Cash (Wise)
  1010  Cash (Bank - via Plaid)
  1100  Accounts Receivable (Stripe)
  1200  Prepaid Expenses
  1300  Inventory
  1500  Computer Equipment (CCA Class 50)
  1510  Furniture & Equipment (CCA Class 8)
  1520  Vehicles (CCA Class 10/10.1)
  ...

2000–2999  Liabilities
  2000  Accounts Payable
  2100  HST/GST Payable
  2150  HST/GST Receivable (ITCs)
  2200  Corporate Tax Payable
  2300  Deferred Revenue
  2400  Shareholder Loan
  2500  Loans Payable
  ...

3000–3999  Equity
  3000  Share Capital
  3100  Retained Earnings
  3200  Dividends Declared
  ...

4000–4999  Revenue
  4000  Sales Revenue
  4100  Service Revenue
  ...

5000–5999  Expenses
  (created lazily as needed — Rent, Utilities, 
   Software, Meals, Travel, Professional Fees, 
   Stripe Fees, Bank Fees, etc.)

6000–6999  Other
  6000  FX Gains/Losses
  6100  Interest Expense
  6200  CCA Expense
```

Accounts in the 5000 range are lazily instantiated — the CoA Manager creates them when first referenced.

### 0.4 — CoA Manager Module

Handles auto-creation of accounts:

```python
# Pseudocode
class CoAManager:
    # Maps common expense categories to account templates
    TEMPLATE_MAP = {
        "rent": ("5200", "Rent Expense", "expense", "operating"),
        "software": ("5300", "Software & Subscriptions", "expense", "operating"),
        "meals": ("5400", "Meals & Entertainment", "expense", "operating"),
        # ... etc
    }
    
    def get_or_create_account(self, org_id, category: str) -> Account:
        existing = lookup_by_category(org_id, category)
        if existing:
            return existing
        
        template = self.TEMPLATE_MAP.get(category)
        if template:
            account = create_account(org_id, *template)
            notify_user(f"Created new account: {account.name}")
            return account
        
        raise NeedsUserInput(f"Unknown category: {category}")
```

### Deliverable: Phase 0

A working accounting engine where you can programmatically create journal entries, query balances, generate a trial balance, and see a basic balance sheet and income statement. No UI yet — just a well-tested Python module with CLI or test scripts.

---

## Phase 1: Rule Engine (Weeks 4–7)

**Goal:** Encode all the deterministic business logic that turns classified events into correct accounting entries.

### 1.1 — Journal Entry Templates

For each use case, define the exact entry pattern:

```python
# Example: Operating Expense (simple)
def record_operating_expense(amount, account, date, vendor, tax_amount=None):
    lines = [
        DebitLine(account=account, amount=amount),
        CreditLine(account="Cash" or "AP", amount=amount),
    ]
    if tax_amount:  # HST/GST ITC
        lines.append(DebitLine(account="HST Receivable (ITC)", amount=tax_amount))
        lines[0].amount -= tax_amount  # net of tax
    return JournalEntry(date=date, description=f"{vendor}", lines=lines)

# Example: Dividend Declaration
def declare_dividend(amount, shareholder, date):
    resolution = generate_resolution("dividend", amount=amount, 
                                      shareholder=shareholder, date=date)
    entry = JournalEntry(
        lines=[
            DebitLine(account="Retained Earnings", amount=amount),
            CreditLine(account="Dividends Payable", amount=amount),
        ]
    )
    return entry, resolution

# Example: Dividend Payment
def pay_dividend(amount, shareholder, date):
    entry = JournalEntry(
        lines=[
            DebitLine(account="Dividends Payable", amount=amount),
            CreditLine(account="Cash", amount=amount),
        ]
    )
    queue_t5_slip(shareholder, amount, tax_year=date.year)
    return entry
```

Build templates for every use case in the SLC scope. This is the most labor-intensive but most critical phase.

### 1.2 — CCA Calculation Engine

```python
class CCAEngine:
    CCA_CLASSES = {
        1:  {"rate": 0.04, "description": "Buildings acquired after 1987"},
        8:  {"rate": 0.20, "description": "Furniture, equipment, machinery"},
        10: {"rate": 0.30, "description": "Vehicles, automotive equipment"},
        10.1: {"rate": 0.30, "description": "Passenger vehicles > $37,000"},
        12: {"rate": 1.00, "description": "Tools, medical instruments < $500"},
        14: {"rate": None, "description": "Patents, franchises, licences (straight-line)"},
        50: {"rate": 0.55, "description": "Computer hardware & software"},
        # ... full CRA table
    }
    
    def calculate_annual_cca(self, asset, fiscal_year):
        ucc_opening = get_ucc_opening(asset, fiscal_year)
        
        # Half-year rule: in acquisition year, CCA base = 50% of net additions
        if asset.acquisition_date.year == fiscal_year:
            cca_base = asset.acquisition_cost * 0.5
        else:
            cca_base = ucc_opening
        
        # Accelerated Investment Incentive Property (AIIP) if applicable
        # (Check dates and eligibility)
        
        cca_amount = cca_base * self.CCA_CLASSES[asset.cca_class]["rate"]
        
        return CCAScheduleEntry(
            ucc_opening=ucc_opening,
            additions=asset.acquisition_cost if acquisition_year else 0,
            cca_claimed=cca_amount,
            ucc_closing=ucc_opening - cca_amount,
            half_year_rule_applied=(asset.acquisition_date.year == fiscal_year),
        )
```

### 1.3 — Proration Engine

Handles deferred revenue and prepaid expenses:

```python
class ProrationEngine:
    def create_schedule(self, total_amount, start_date, end_date, 
                         debit_account, credit_account):
        """Generate monthly amortization entries."""
        months = months_between(start_date, end_date)
        entries = []
        
        for month_start, month_end in months:
            # Pro-rate partial first/last months by day count
            days_in_period = (end_date - start_date).days
            days_in_month = (month_end - month_start).days
            month_amount = total_amount * (days_in_month / days_in_period)
            
            entries.append(ScheduledEntry(
                date=month_end,
                debit=debit_account,   # e.g., "Software Expense"
                credit=credit_account,  # e.g., "Prepaid Expenses"
                amount=round(month_amount, 2),
            ))
        
        # Adjust final entry for rounding to ensure total matches
        adjust_rounding(entries, total_amount)
        return entries
```

### 1.4 — HST/GST Tracking Module

- Track tax collected on sales (liability)
- Track ITCs on purchases (receivable)
- Calculate net owing per reporting period
- Generate summary for filing

### 1.5 — Shareholder Loan Tracker

- Automatically detect shareholder loan events (personal expense paid by company, company expense paid personally)
- Maintain running balance per shareholder
- **s.15(2) warning**: if balance is outstanding and approaching fiscal year-end + one year, alert the user

### 1.6 — FX Handling

- Record transactions at daily exchange rate (Bank of Canada rate)
- Calculate realized gain/loss when foreign currency is converted
- Unrealized gain/loss at period-end for foreign-denominated balances

### 1.7 — Reconciliation Engine

For matching Stripe payouts to bank deposits:

- Pull payout details from Stripe API (payout → balance transactions → charges)
- Match aggregate payout amount to bank deposit
- Allocate fees (Stripe processing fees, bank fees)
- Flag discrepancies for user review

### 1.8 — Period-End Close

- Close revenue and expense accounts to Retained Earnings
- Book any pending adjusting entries (accruals, CCA, proration catch-ups)
- Generate financial statements
- Lock the period (prevent backdated entries)

### Deliverable: Phase 1

A fully functional rule engine that, given structured input (intent + entities), produces correct journal entries, schedules future entries, generates corporate documents, and maintains all subsidiary ledgers. Testable via unit tests with known inputs/outputs. All CCA classes, HST logic, and proration math covered.

---

## Phase 2: ML Pipeline — Synthetic Data & Models (Weeks 5–9)

**Goal:** Build the NLU and classification models that turn raw inputs (user text, bank descriptions) into structured data the rule engine can consume.

*Note: This phase overlaps with Phase 1 — start data generation while building the rule engine.*

### 2.1 — Define Label Taxonomies

Before generating any data, lock down the label sets:

**Intent labels (~18 intents for SLC):**

```
record_operating_expense      record_capital_expenditure
record_revenue_onetime        record_subscription_revenue
record_refund                 record_inventory_purchase
declare_dividend              pay_dividend
capital_injection             shareholder_loan_to_company
shareholder_loan_from_company record_loan_payment
record_tax_payment            request_financial_statement
request_cca_schedule          record_asset_disposition
record_fx_conversion          general_question
```

**Entity types (~10 types):**

```
AMOUNT          DATE            VENDOR
ASSET_NAME      FREQUENCY       DURATION
SHAREHOLDER     ACCOUNT_NAME    TAX_AMOUNT
DESCRIPTION
```

**Bank transaction categories (~25 categories):**

```
stripe_payout            shopify_payout
wise_fx_conversion       wise_transfer_in
wise_transfer_out        interac_etransfer_in
interac_etransfer_out    cra_hst_payment
cra_corporate_tax        payroll_service
rent                     utilities
software_subscription    office_supplies
meals_entertainment      travel
professional_fees        insurance
interest_bank            bank_fee
loan_payment             shareholder_transfer_in
shareholder_transfer_out unknown
```

### 2.2 — Synthetic Data Generation

#### Step 1: Write Generation Prompts

For each intent, craft a detailed prompt. Example:

```
System: You are generating training data for an NLU model used 
in Canadian small business accounting software.

Generate 80 diverse examples of how a business owner might tell 
the system they purchased a capital asset (equipment, computer, 
vehicle, furniture, etc.).

Requirements:
- Mix of formal ("I'd like to record a purchase") and casual 
  ("got a new laptop")
- Some include price, some don't
- Some include vendor, date — some don't
- Include Canadian-specific things (prices in CAD, Canadian vendors)
- Include some with typos, fragments, abbreviations
- Include some in mixed English/French (common in Canadian businesses)
- Each example on its own line
- After each example, provide the JSON entity annotations

Format per line:
TEXT ||| {"intent": "record_capital_expenditure", "entities": {...}}
```

#### Step 2: Generate at Scale

```python
# generate_training_data.py

INTENTS = [...]  # All 18 intents
EXAMPLES_PER_INTENT = 800  # Generates ~14,400 total

for intent in INTENTS:
    prompt = load_prompt_template(intent)
    
    # Generate in batches of 80 to maintain quality
    for batch in range(10):
        response = claude_api.create(
            model="claude-sonnet-4-20250514",
            prompt=prompt + f"\n\nBatch {batch+1}/10. "
                   f"Make these DIFFERENT from previous batches. "
                   f"Vary sentence structure, vocabulary, specificity.",
            max_tokens=4000,
        )
        parse_and_save(response, intent, batch)
```

Separately generate bank transaction training data:

```python
BANK_CATEGORIES = [...]  # All 25 categories

# Bank transactions are short/cryptic — different prompt style
prompt = """
Generate 100 realistic Canadian bank/credit card statement 
descriptions for the category: {category}

These should look EXACTLY like real bank statements:
- Truncated merchant names (e.g., "AMZN MKTP CA*2K1")
- Merchant location codes
- Reference numbers
- ALL CAPS (most banks)
- Mix of English and French
- Include realistic amounts

Format: DESCRIPTION ||| AMOUNT
"""
```

#### Step 3: Quality Control

```python
# Automated checks
def validate_training_data(examples):
    for ex in examples:
        assert ex.intent in VALID_INTENTS
        assert all(e.type in VALID_ENTITY_TYPES for e in ex.entities)
        assert len(ex.text) > 3  # Not empty
        # Check for duplicates
        # Check for label consistency

# Manual review: randomly sample 5% and verify labels
# Fix systematic errors, then re-generate if needed
```

#### Step 4: Data Augmentation

```python
# Noise injection for robustness
def augment(text):
    augmentations = [
        random_typo,          # "bougth" instead of "bought"
        drop_random_word,     # "bought laptop $2400" → "bought $2400"
        lowercase_all,        # "I Bought A MacBook" → "i bought a macbook"
        remove_punctuation,   # Remove commas, periods
        swap_currency_format, # "$2,400" ↔ "2400$" ↔ "2400 dollars"
        abbreviate,           # "subscription" → "sub"
    ]
    return random.choice(augmentations)(text)
```

#### Data Generation Summary

| Dataset | Size | Est. API Cost |
|---------|------|---------------|
| Intent + Entity training data | ~14,400 examples | ~$40–60 |
| Bank transaction data | ~5,000 examples | ~$15–25 |
| Augmented variants | ~10,000 additional | $0 (local) |
| **Total** | **~30,000 examples** | **~$55–85** |

### 2.3 — Model Training

#### Intent Classification (DeBERTa-v3-base)

```python
# Fine-tune DeBERTa-v3-base for intent classification
from transformers import AutoModelForSequenceClassification, Trainer

model = AutoModelForSequenceClassification.from_pretrained(
    "microsoft/deberta-v3-base",
    num_labels=len(INTENT_LABELS),
)

trainer = Trainer(
    model=model,
    train_dataset=intent_train_dataset,
    eval_dataset=intent_eval_dataset,
    # Hyperparams: lr=2e-5, epochs=5, batch_size=16
)
trainer.train()
```

Target: **>95% accuracy** on held-out test set.

#### Entity Extraction (DeBERTa-v3-base token classification + SpaCy)

Two-stage approach:

```python
# Stage 1: SpaCy rules for structured entities
# (amounts, dates, currency — these have reliable patterns)
import spacy
nlp = spacy.blank("en")
ruler = nlp.add_pipe("entity_ruler")
patterns = [
    {"label": "AMOUNT", "pattern": [{"LIKE_NUM": True}]},
    {"label": "AMOUNT", "pattern": [{"TEXT": "$"}, {"LIKE_NUM": True}]},
    # ... date patterns, currency patterns
]

# Stage 2: DeBERTa for semantic entities
# (vendor names, asset descriptions, frequencies)
model = AutoModelForTokenClassification.from_pretrained(
    "microsoft/deberta-v3-base",
    num_labels=len(BIO_LABELS),  # B-VENDOR, I-VENDOR, B-ASSET, ...
)
```

#### Bank Transaction Classifier (DeBERTa-v3-small)

```python
# Smaller model — bank descriptions are short
model = AutoModelForSequenceClassification.from_pretrained(
    "microsoft/deberta-v3-small",
    num_labels=len(BANK_CATEGORIES),
)
# Train similarly to intent classifier
```

Target: **>90% accuracy** (with confidence threshold — low-confidence items go to user review).

#### CCA Class Matcher (Sentence-Transformer)

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

# Pre-encode CCA class descriptions
cca_descriptions = {
    50: "Computer hardware, systems software, and related equipment",
    8: "Office furniture, fixtures, equipment, machinery, tools over $500",
    10: "Motor vehicles, automobiles, trucks, vans",
    # ... all classes
}
cca_embeddings = {k: model.encode(v) for k, v in cca_descriptions.items()}

# At inference: encode asset description, find nearest CCA class
def classify_cca(asset_description):
    embedding = model.encode(asset_description)
    similarities = {k: cosine_sim(embedding, v) for k, v in cca_embeddings.items()}
    best_match = max(similarities, key=similarities.get)
    confidence = similarities[best_match]
    return best_match, confidence
```

No fine-tuning needed — this works out of the box with good descriptions.

### 2.4 — Model Serving

```python
# Serve all models via FastAPI endpoints (internal)
# In production, consider ONNX conversion for faster inference

from optimum.onnxruntime import ORTModelForSequenceClassification

# Convert for ~2-3x inference speedup
ort_model = ORTModelForSequenceClassification.from_pretrained(
    "./trained_intent_model",
    export=True,
)
```

### Deliverable: Phase 2

Trained and validated models for intent classification, entity extraction, bank transaction classification, and CCA class matching. Served via internal API. Confidence thresholds calibrated on evaluation set.

---

## Phase 3: Integrations (Weeks 7–10)

**Goal:** Connect to external payment platforms and banking services.

### 3.1 — Adapter Framework

```python
# Base adapter interface
class PaymentPlatformAdapter(ABC):
    @abstractmethod
    def normalize_event(self, raw_event: dict) -> NormalizedFinancialEvent:
        """Convert platform-specific webhook to standard format."""
        pass
    
    @abstractmethod
    def verify_webhook(self, request) -> bool:
        """Verify webhook signature."""
        pass

class NormalizedFinancialEvent:
    event_type: str  # "payment_received" | "payout" | "refund" | ...
    source: str      # "stripe" | "wise" | ...
    source_model: str  # "processor" | "merchant_of_record"
    gross_amount: Decimal
    fees: list[Fee]
    net_amount: Decimal
    tax_collected: Optional[Decimal]  # None for MoR
    line_items: list[LineItem]
    currency: str
    timestamp: datetime
    external_id: str  # Platform's transaction ID
```

### 3.2 — Stripe Integration

Priority webhooks to handle:

```
invoice.paid          → Record revenue (accrual)
invoice.payment_failed → Flag for follow-up
charge.refunded       → Record refund
payout.paid           → Trigger bank reconciliation
customer.subscription.created  → Set up deferred revenue schedule
customer.subscription.deleted  → Close out deferred revenue
```

Also: Stripe Connect API to pull historical data on first sync.

### 3.3 — Wise Integration

- Transaction webhooks for incoming/outgoing transfers
- Balance API for multi-currency positions
- Exchange rate at time of conversion (for FX gain/loss)

### 3.4 — Plaid/Flinks Integration

- Transaction sync (pull new transactions daily or via webhook)
- Feed into bank transaction classifier (Layer 1)
- Use Plaid's merchant categorization as supplementary signal

### 3.5 — Reconciliation Pipeline

```python
async def reconcile_stripe_payout(payout_event, bank_transactions):
    # 1. Get payout details from Stripe
    payout = stripe.Payout.retrieve(payout_event.payout_id,
                                      expand=["balance_transaction"])
    
    # 2. Get all balance transactions in this payout
    balance_txns = stripe.BalanceTransaction.list(payout=payout.id)
    
    # 3. Match to bank deposit (by amount + date range)
    bank_match = find_matching_deposit(bank_transactions, 
                                        payout.amount, payout.arrival_date)
    
    # 4. Create reconciliation record
    if bank_match and abs(bank_match.amount - payout.amount) < THRESHOLD:
        auto_reconcile(payout, balance_txns, bank_match)
    else:
        flag_for_review(payout, bank_match)
```

### Deliverable: Phase 3

Working integrations with Stripe, Wise, and Plaid. Webhooks received, normalized, and processed through the rule engine. Reconciliation matching operational. Bank transactions classified and journal entries auto-generated.

---

## Phase 4: User Interface (Weeks 8–12)

**Goal:** A clean, conversational-first interface that makes the system lovable.

### 4.1 — Conversational Input

The primary interaction mode. A chat-like interface where the user types business events:

```
User: "I bought a laptop for $2,400 at Best Buy"

System: Got it! Here's what I'll record:
  
  📦 Capital Asset: Laptop (CCA Class 50, 55% rate)
  
  Dr. Computer Equipment     $2,123.89
  Dr. HST Receivable (ITC)     $276.11
      Cr. Cash                          $2,400.00
  
  📅 CCA of $584.07 will be claimed this fiscal year 
     (half-year rule applied)
  
  [✅ Approve]  [✏️ Edit]  [❌ Cancel]
```

### 4.2 — Dashboard

Minimal but informative:

- **Cash position** (across all connected accounts)
- **Revenue this month/quarter/year** (with trend)
- **Upcoming obligations** (HST remittance due, tax installment, etc.)
- **Review queue** (items needing user confirmation)
- **Shareholder loan balance** (with warning if applicable)

### 4.3 — Review Queue

All items below the confidence threshold, or items requiring legal approval (dividends):

- Unclassified bank transactions
- Low-confidence expense categorizations
- Reconciliation discrepancies
- Dividend declarations (always require explicit approval)

### 4.4 — Financial Statements View

- Balance Sheet, Income Statement, Trial Balance
- Filterable by date range
- Drill-down from any line item to the underlying journal entries
- Export to PDF or CSV

### 4.5 — CCA Schedule View

- All assets by class
- UCC balances, CCA claimed per year
- Visual timeline of depreciation

### Deliverable: Phase 4

A functional web application where users can connect their accounts, chat with the system, review and approve entries, and view their financial statements.

---

## Phase 5: CFO Advisory Layer (Weeks 11–14)

**Goal:** The "proactive intelligence" that makes this more than a bookkeeping tool.

### 5.1 — Periodic Analysis (Celery Scheduled Tasks)

```python
# Run weekly or monthly
@celery.task
def generate_advisory_insights(org_id):
    financials = get_current_financials(org_id)
    assets = get_asset_register(org_id)
    shareholder_loan = get_shareholder_loan_balance(org_id)
    
    # Build context for LLM
    context = format_financial_summary(financials, assets, shareholder_loan)
    
    insights = claude_api.create(
        model="claude-sonnet-4-20250514",
        system=CFO_ADVISOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )
    
    # Parse and store actionable insights
    store_insights(org_id, insights)
```

### 5.2 — Types of Proactive Nudges

- **"You haven't claimed CCA this year"** — reminder before fiscal year-end
- **"Retained earnings are building up"** — suggest dividend planning
- **"HST remittance due in 2 weeks"** — upcoming deadline
- **"Your shareholder loan is approaching the s.15(2) deadline"** — urgent warning
- **"Expenses in [category] are 40% higher than last quarter"** — anomaly detection
- **"You may qualify for the small business deduction on your first $500K"** — tax optimization

### 5.3 — Explainability

When the system auto-records an entry, the user can ask "why did you do that?" and get a plain-English explanation:

```
User: "Why did you split that $1,200 payment into 12 entries?"

System: "You told me you paid $1,200 for a yearly Figma 
subscription starting March 1. Under accrual accounting 
(ASPE), we recognize expenses in the period they're consumed, 
not when cash is paid. So I recorded a $1,200 prepaid asset 
on March 1, and I'm moving $100/month to Software Expense 
over the subscription term. This gives you a more accurate 
picture of your monthly costs."
```

This is a great use of the LLM — it already has all the context (the entry, the rule that triggered it) and just needs to explain in human terms.

### Deliverable: Phase 5

Working advisory system that periodically analyzes the user's financials and surfaces actionable suggestions. Explanation capability for any system-generated entry.

---

## Phase 6: Testing, Compliance & Launch Prep (Weeks 13–16)

### 6.1 — Accounting Accuracy Testing

- **Known-answer tests**: Create test companies with known transactions and verify every journal entry, financial statement, CCA calculation, and tax figure matches expected output
- **Edge cases**: partial-year CCA, asset disposition mid-year, refund after revenue recognition, FX conversion timing, HST on mixed-supply, shareholder loan across fiscal years
- **Reconciliation**: simulate realistic Stripe payout batches with multiple charges, refunds, and disputes

### 6.2 — ML Model Evaluation

- Held-out test set (generated from DIFFERENT prompt templates than training data)
- Confusion matrix analysis — which intents get confused?
- Confidence calibration — ensure the confidence threshold correctly routes uncertain items to user review
- Adversarial testing — weird inputs, edge cases, non-English text

### 6.3 — Security

- **Encryption at rest** for all financial data
- **Encryption in transit** (TLS everywhere)
- **API credential vault** (don't store Stripe/Wise keys in plaintext)
- **Audit log** — every action, every entry, every approval is logged with timestamp and actor
- **Role-based access** (for multi-user in future)

### 6.4 — Disclaimer & Legal

This software is not a CPA. Include appropriate disclaimers:

- "This software assists with bookkeeping and corporate record-keeping. It does not constitute professional accounting or legal advice."
- "Review financial statements with a qualified accountant before filing."
- "Corporate resolutions generated by this software should be reviewed by legal counsel."

### Deliverable: Phase 6

A tested, secure, launch-ready product with comprehensive test coverage on accounting logic, validated ML models, and appropriate legal disclaimers.

---

## Indicative Timeline (Solo Developer)

| Phase | Duration | Weeks | Dependencies |
|-------|----------|-------|--------------|
| **Phase 0:** Foundation | 3 weeks | 1–3 | None |
| **Phase 1:** Rule Engine | 4 weeks | 4–7 | Phase 0 |
| **Phase 2:** ML Pipeline | 5 weeks | 5–9 | Overlaps Phase 1 (data gen starts early) |
| **Phase 3:** Integrations | 4 weeks | 7–10 | Phase 0, Phase 1 (partial) |
| **Phase 4:** UI | 5 weeks | 8–12 | Phases 0–3 (backend functional) |
| **Phase 5:** CFO Advisory | 4 weeks | 11–14 | Phases 0–3 |
| **Phase 6:** Testing & Launch | 4 weeks | 13–16 | All above |

**Total: approximately 16 weeks (4 months) to SLC with significant parallel work.**

Adjust expectations if working part-time alongside other commitments. A realistic part-time estimate would be 6–8 months.

---

## Cost Estimates (Pre-Revenue)

| Item | Monthly Cost |
|------|-------------|
| Hosting (Railway/Fly.io — API + DB + Redis) | $25–50 |
| GPU for ML inference (small instance or serverless) | $20–40 |
| Stripe/Wise/Plaid API | Free tier (Plaid: 100 connections free for dev) |
| Claude API for advisory layer | $10–30 (very low volume initially) |
| Domain + misc | $15 |
| **Total pre-revenue** | **~$70–135/month** |

Synthetic data generation is a one-time cost of ~$55–85.

---

## Open Questions for Future Decisions

1. **Pricing model** — per-transaction? Monthly flat fee? Freemium with premium features?
2. **Multi-province HST/PST/QST** — v1 could start with a single province, expand later
3. **When to add payroll** — integrate with a payroll provider (Wagepoint, Humi) vs. build it
4. **When to add s.85 / stock options** — these are high-value but need deep tax law modeling
5. **US/international expansion** — different GAAP, different tax code, different CCA-equivalent
6. **CRA e-filing integration** — eventually file HST returns and T2 directly? Big compliance hurdle
7. **Accountant collaboration mode** — let the user's CPA log in and review/adjust entries
