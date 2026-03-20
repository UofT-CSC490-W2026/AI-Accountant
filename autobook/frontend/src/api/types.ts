export type Status = "auto_posted" | "needs_clarification" | "rejected" | "accepted";

export type RealtimeEvent = {
  type: "entry.posted" | "clarification.created" | "clarification.resolved";
  journal_entry_id: string;
  occurred_at: string;
};

export type ParseAccepted = {
  parse_id: string;
  status: "accepted";
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
  source: "manual" | "upload" | "bank_feed";
  currency?: string;
};

export type ClarificationItem = {
  clarification_id: string;
  status: "pending" | "resolved" | "rejected";
  source_text: string;
  explanation: string;
  confidence: {
    overall: number;
  };
  proposed_entry: {
    lines: JournalLine[];
  };
};

export type ClarificationsResponse = {
  items: ClarificationItem[];
  count: number;
};

export type ResolveClarificationRequest = {
  action: "approve" | "edit" | "reject";
  edited_entry?: {
    lines: JournalLine[];
    explanation?: string;
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
