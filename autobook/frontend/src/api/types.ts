export type Status = "auto_posted" | "needs_clarification" | "rejected" | "accepted";

export type TransactionInputSource = "manual_text" | "csv_upload" | "pdf_upload" | "bank_feed";

export type AuthUser = {
  id: string;
  cognito_sub: string;
  email: string;
  role: string;
  role_source: string;
  token_use: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  id_token?: string | null;
  refresh_token?: string | null;
};

export type ParseAccepted = {
  parse_id: string;
  status: "accepted";
  statement_count?: number;
};

export type BatchItem = {
  child_parse_id: string;
  statement_index: number;
  input_text?: string | null;
  status: string;
  clarification_id?: string | null;
  journal_entry_id?: string | null;
  error?: string | null;
};

export type BatchSummary = {
  total_statements: number;
  completed_statements: number;
  pending_statements: number;
  auto_posted_count: number;
  needs_clarification_count: number;
  resolved_count: number;
  rejected_count: number;
  failed_count: number;
  status: string;
  items: BatchItem[];
};

export type ParseStatus = {
  parse_id: string;
  status:
    | "accepted"
    | "processing"
    | "auto_posted"
    | "needs_clarification"
    | "resolved"
    | "rejected"
    | "failed";
  stage?: string | null;
  occurred_at: string;
  updated_at: string;
  input_text?: string | null;
  explanation?: string | null;
  confidence?: {
    overall: number;
    auto_post_threshold?: number;
  } | null;
  proposed_entry?: {
    journal_entry_id?: string | null;
    lines: JournalLine[];
  } | null;
  clarification_id?: string | null;
  journal_entry_id?: string | null;
  error?: string | null;
  batch?: BatchSummary | null;
};

export type JournalLine = {
  account_code: string;
  account_name: string;
  type: "debit" | "credit";
  amount: number;
};

export type ParseResponse = {
  parse_id: string;
  status: Status;
  explanation: string;
  confidence: {
    overall: number;
    auto_post_threshold?: number;
  };
  parse_time_ms?: number;
  proposed_entry: {
    journal_entry_id?: string | null;
    lines: JournalLine[];
  };
  clarification_id?: string | null;
};

export type ParseRequest = {
  input_text: string;
  source: Extract<TransactionInputSource, "manual_text" | "bank_feed">;
  currency?: string;
  stages?: string[];
  store?: boolean;
  post_stages?: string[];
};

export type ClarificationItem = {
  clarification_id: string;
  status: "pending" | "resolved" | "rejected";
  source_text: string;
  explanation: string;
  confidence: {
    overall: number;
  };
  proposed_entry?: {
    journal_entry_id?: string | null;
    lines: JournalLine[];
  } | null;
};

export type ClarificationsResponse = {
  items: ClarificationItem[];
  count: number;
};

export type ResolveClarificationRequest = {
  action: "approve" | "edit" | "reject";
  edited_entry?: {
    journal_entry_id?: string | null;
    lines: JournalLine[];
  };
};

export type ResolveClarificationResponse = {
  clarification_id: string;
  status: "resolved" | "rejected";
  journal_entry_id?: string;
};

export type LedgerEntry = {
  journal_entry_id: string;
  date: string;
  occurred_at?: string;
  description: string;
  status: "posted";
  lines: JournalLine[];
};

export type AccountBalance = {
  account_code: string;
  account_name: string;
  balance: number;
};

export type LedgerResponse = {
  entries: LedgerEntry[];
  balances: AccountBalance[];
  summary: {
    total_debits: number;
    total_credits: number;
  };
};

export type StatementSection = {
  title: string;
  rows: Array<{
    label: string;
    amount: number;
  }>;
};

export type StatementsResponse = {
  statement_type: "balance_sheet" | "income_statement" | "trial_balance";
  period: {
    as_of?: string;
    from?: string;
    to?: string;
  };
  sections: StatementSection[];
  totals: Record<string, number>;
};

export type RealtimeEvent = {
  type: "entry.posted" | "clarification.created" | "clarification.resolved" | "pipeline.result" | "pipeline.error" | "pipeline.stage_started" | "pipeline.stage_skipped";
  journal_entry_id?: string;
  parse_id?: string;
  input_text?: string;
  occurred_at: string;
  confidence?: { overall: number };
  explanation?: string;
  status?: string;
  proposed_entry?: { lines: JournalLine[] };
  parse_time_ms?: number;
  stage?: string;
  result?: Record<string, unknown>;
  error?: string;
  batch?: BatchSummary;
};

export type RealtimeListener = (event: RealtimeEvent) => void;
