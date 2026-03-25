-- =============================================================================
-- FULL SCHEMA CREATION — run once against a fresh database
-- =============================================================================
-- Generated from SQLAlchemy models. Run this in pgAdmin Query Tool.

BEGIN;

-- ── Enum types ──────────────────────────────────────────────────────────────

CREATE TYPE integrationplatform AS ENUM ('stripe', 'wise', 'plaid', 'shopify', 'lemonsqueezy', 'paddle');
CREATE TYPE integrationstatus AS ENUM ('active', 'inactive', 'error');
CREATE TYPE documenttype AS ENUM ('dividend_resolution', 'directors_resolution', 'annual_return', 'articles_of_amendment', 't5_slip');
CREATE TYPE documentstatus AS ENUM ('draft', 'signed');
CREATE TYPE reconciliationstatus AS ENUM ('auto_matched', 'user_confirmed', 'manual', 'discrepancy');
CREATE TYPE taxtype AS ENUM ('hst', 'gst', 'pst', 'corporate_income');
CREATE TYPE taxobligationstatus AS ENUM ('accruing', 'calculated', 'filed', 'paid');

-- ── Independent tables ──────────────────────────────────────────────────────

CREATE TABLE calibration_params (
    id UUID NOT NULL PRIMARY KEY,
    a FLOAT NOT NULL,
    b FLOAT NOT NULL,
    sample_count INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE organizations (
    id UUID NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    incorporation_date DATE,
    fiscal_year_end DATE NOT NULL,
    jurisdiction VARCHAR(50) NOT NULL,
    hst_registration_number VARCHAR(50),
    business_number VARCHAR(20),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE users (
    id UUID NOT NULL PRIMARY KEY,
    cognito_sub VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    last_authenticated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX ix_users_cognito_sub ON users (cognito_sub);
CREATE INDEX ix_users_email ON users (email);

-- ── Tables depending on users ───────────────────────────────────────────────

CREATE TABLE assets (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    acquisition_date DATE NOT NULL,
    acquisition_cost NUMERIC(15, 2) NOT NULL,
    cca_class VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE auth_sessions (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    cognito_sub VARCHAR(255) NOT NULL,
    token_fingerprint VARCHAR(64) NOT NULL,
    token_use VARCHAR(20) NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE chart_of_accounts (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    auto_created BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT uq_chart_of_accounts_user_code UNIQUE (user_id, account_code),
    CONSTRAINT ck_chart_of_accounts_account_type CHECK (account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense'))
);

CREATE TABLE scheduled_entries (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    amount NUMERIC(15, 2),
    frequency VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    next_run_date DATE NOT NULL,
    template_journal_entry JSONB NOT NULL,
    source VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE transactions (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    normalized_description TEXT,
    amount NUMERIC(15, 2),
    currency VARCHAR(3) DEFAULT 'CAD' NOT NULL,
    date DATE NOT NULL,
    source VARCHAR(50) NOT NULL,
    counterparty VARCHAR(255),
    amount_mentions JSONB,
    date_mentions JSONB,
    party_mentions JSONB,
    quantity_mentions JSONB,
    intent_label VARCHAR(100),
    entities JSONB,
    bank_category VARCHAR(100),
    cca_class_match VARCHAR(50),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- ── Tables depending on transactions ────────────────────────────────────────

CREATE TABLE clarification_tasks (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES transactions (id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    source_text TEXT NOT NULL,
    explanation TEXT NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL,
    proposed_entry JSONB,
    evaluator_verdict VARCHAR(20) NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE journal_entries (
    id UUID NOT NULL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES transactions (id) ON DELETE SET NULL,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'draft' NOT NULL,
    origin_tier INTEGER,
    confidence NUMERIC(4, 3),
    rationale TEXT,
    posted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT ck_journal_entries_status CHECK (status IN ('draft', 'posted')),
    CONSTRAINT ck_journal_entries_origin_tier CHECK (origin_tier IS NULL OR origin_tier BETWEEN 1 AND 4),
    CONSTRAINT ck_journal_entries_confidence CHECK (confidence IS NULL OR (confidence >= 0.000 AND confidence <= 1.000))
);

-- ── Tables depending on journal_entries ─────────────────────────────────────

CREATE TABLE journal_lines (
    id UUID NOT NULL PRIMARY KEY,
    journal_entry_id UUID NOT NULL REFERENCES journal_entries (id) ON DELETE CASCADE,
    account_code VARCHAR(20) NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    type VARCHAR(10) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    line_order INTEGER DEFAULT 0 NOT NULL,
    CONSTRAINT ck_journal_lines_type CHECK (type IN ('debit', 'credit')),
    CONSTRAINT ck_journal_lines_amount_positive CHECK (amount > 0)
);

CREATE TABLE cca_schedule_entries (
    id UUID NOT NULL PRIMARY KEY,
    asset_id UUID NOT NULL REFERENCES assets (id) ON DELETE CASCADE,
    fiscal_year INTEGER NOT NULL,
    ucc_opening NUMERIC(15, 2) NOT NULL,
    additions NUMERIC(15, 2) DEFAULT 0 NOT NULL,
    dispositions NUMERIC(15, 2) DEFAULT 0 NOT NULL,
    cca_claimed NUMERIC(15, 2) NOT NULL,
    ucc_closing NUMERIC(15, 2) NOT NULL,
    half_year_rule_applied BOOLEAN DEFAULT false NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries (id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

-- ── Tables depending on organizations ───────────────────────────────────────

CREATE TABLE integration_connections (
    id UUID NOT NULL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    platform integrationplatform NOT NULL,
    credentials TEXT,
    status integrationstatus NOT NULL,
    last_sync TIMESTAMP WITHOUT TIME ZONE,
    webhook_secret VARCHAR(255),
    config JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE corporate_documents (
    id UUID NOT NULL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    document_type documenttype NOT NULL,
    date DATE NOT NULL,
    description TEXT,
    generated_file_path VARCHAR(500),
    related_journal_entry_id UUID REFERENCES journal_entries (id),
    status documentstatus NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE reconciliation_records (
    id UUID NOT NULL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    bank_transaction_id VARCHAR(255),
    platform_transaction_ids VARCHAR(255)[],
    status reconciliationstatus NOT NULL,
    matched_amount NUMERIC(19, 4),
    discrepancy_amount NUMERIC(19, 4),
    journal_entry_id UUID REFERENCES journal_entries (id),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE shareholder_loan_ledger (
    id UUID NOT NULL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    shareholder_name VARCHAR(255) NOT NULL,
    transaction_date DATE NOT NULL,
    amount NUMERIC(19, 4) NOT NULL,
    description TEXT,
    journal_entry_id UUID REFERENCES journal_entries (id),
    running_balance NUMERIC(19, 4) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE tax_obligations (
    id UUID NOT NULL PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
    tax_type taxtype NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    amount_collected NUMERIC(19, 4) NOT NULL,
    itcs_claimed NUMERIC(19, 4) NOT NULL,
    net_owing NUMERIC(19, 4) NOT NULL,
    status taxobligationstatus NOT NULL,
    payment_journal_entry_id UUID REFERENCES journal_entries (id),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL
);

COMMIT;
