import clarificationResolvedFixture from "./fixtures/clarification-resolved.json";
import clarificationsPendingFixture from "./fixtures/clarifications-pending.json";
import ledgerFixture from "./fixtures/ledger-sample.json";
import parseAutoPostedFixture from "./fixtures/parse-auto-posted.json";
import parseNeedsClarificationFixture from "./fixtures/parse-needs-clarification.json";
import statementsFixture from "./fixtures/statements-sample.json";
import type {
  ClarificationItem,
  ClarificationsResponse,
  LedgerEntry,
  LedgerResponse,
  ParseAccepted,
  ParseRequest,
  ParseResponse,
  RealtimeEvent,
  RealtimeListener,
  ResolveClarificationRequest,
  ResolveClarificationResponse,
  StatementType,
  StatementsResponse,
  TransactionInputSource,
} from "../api/types";

function createInitialClarifications() {
  return structuredClone(clarificationsPendingFixture.items) as ClarificationItem[];
}

function createInitialLedgerEntries() {
  return structuredClone(ledgerFixture.entries) as LedgerEntry[];
}

let clarificationsStore = createInitialClarifications();
let ledgerEntriesStore = createInitialLedgerEntries();
const realtimeListeners = new Set<RealtimeListener>();

let parseSequence = 3000;
let clarificationSequence = 3000;
let journalEntrySequence = 3000;

function delay(ms = 350) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getTodayDate() {
  return new Date().toISOString().slice(0, 10);
}

function getCurrentTimestamp() {
  return new Date().toISOString();
}

function deriveUploadSource(file: File): Extract<TransactionInputSource, "csv_upload" | "pdf_upload"> {
  const lowerName = file.name.toLowerCase();
  if (file.type === "text/csv" || lowerName.endsWith(".csv")) {
    return "csv_upload";
  }

  if (file.type === "application/pdf" || lowerName.endsWith(".pdf")) {
    return "pdf_upload";
  }

  throw new Error("Unsupported file type. Upload a CSV or text-based PDF.");
}

function nextParseId() {
  parseSequence += 1;
  return `parse_${parseSequence}`;
}

function nextClarificationId() {
  clarificationSequence += 1;
  return `cl_${clarificationSequence}`;
}

function nextJournalEntryId() {
  journalEntrySequence += 1;
  return `je_${journalEntrySequence}`;
}

function emitRealtimeUpdate(event: RealtimeEvent) {
  const snapshot = structuredClone(event) as RealtimeEvent;
  for (const listener of realtimeListeners) {
    listener(snapshot);
  }
}

function scheduleRealtimeUpdate(event: RealtimeEvent) {
  const snapshot = structuredClone(event) as RealtimeEvent;
  setTimeout(() => {
    emitRealtimeUpdate(snapshot);
  }, 10);
}

export function subscribeToRealtimeUpdates(listener: RealtimeListener) {
  realtimeListeners.add(listener);

  return () => {
    realtimeListeners.delete(listener);
  };
}

export function resetMockApiState() {
  clarificationsStore = createInitialClarifications();
  ledgerEntriesStore = createInitialLedgerEntries();
  realtimeListeners.clear();
  parseSequence = 3000;
  clarificationSequence = 3000;
  journalEntrySequence = 3000;
}

function computeLedgerSummary(entries: LedgerEntry[]): LedgerResponse["summary"] {
  let totalDebits = 0;
  let totalCredits = 0;

  for (const entry of entries) {
    for (const line of entry.lines) {
      if (line.type === "debit") {
        totalDebits += line.amount;
      } else {
        totalCredits += line.amount;
      }
    }
  }

  return {
    total_debits: totalDebits,
    total_credits: totalCredits,
  };
}

function computeBalances(entries: LedgerEntry[]): LedgerResponse["balances"] {
  const balanceMap = new Map<string, { account_code: string; account_name: string; balance: number }>();

  for (const entry of entries) {
    for (const line of entry.lines) {
      const current = balanceMap.get(line.account_code) ?? {
        account_code: line.account_code,
        account_name: line.account_name,
        balance: 0,
      };

      current.balance += line.type === "debit" ? line.amount : -line.amount;
      balanceMap.set(line.account_code, current);
    }
  }

  return Array.from(balanceMap.values()).sort((left, right) =>
    left.account_code.localeCompare(right.account_code),
  );
}

function buildBalanceSheetFromLedger(entries: LedgerEntry[]): StatementsResponse {
  const balances = computeBalances(entries);
  const assetRows = ["1000", "1100", "1500"]
    .map((accountCode) => balances.find((balance) => balance.account_code === accountCode))
    .filter((balance): balance is NonNullable<typeof balance> => Boolean(balance))
    .map((balance) => ({
      label: balance.account_name,
      amount: balance.balance,
    }));

  const fallbackAssets =
    structuredClone(statementsFixture.sections.find((section) => section.title === "Assets")?.rows) ?? [];
  const resolvedAssetRows = assetRows.length > 0 ? assetRows : fallbackAssets;
  const assetsTotal = resolvedAssetRows.reduce((total, row) => total + row.amount, 0);

  return {
    statement_type: "balance_sheet",
    period: {
      as_of: getTodayDate(),
    },
    sections: [
      {
        title: "Assets",
        rows: resolvedAssetRows,
      },
      {
        title: "Equity",
        rows: [
          {
            label: "Owner Equity",
            amount: assetsTotal,
          },
        ],
      },
    ],
    totals: {
      assets: assetsTotal,
      liabilities_and_equity: assetsTotal,
    },
  };
}

function buildIncomeStatementFromLedger(entries: LedgerEntry[]): StatementsResponse {
  const balances = computeBalances(entries);
  const revenueRows = balances
    .filter((balance) => balance.account_code.startsWith("4"))
    .map((balance) => ({
      label: balance.account_name,
      amount: Math.abs(balance.balance),
    }));
  const expenseRows = balances
    .filter((balance) => balance.account_code.startsWith("5") || balance.account_code.startsWith("6"))
    .map((balance) => ({
      label: balance.account_name,
      amount: Math.abs(balance.balance),
    }));

  const totalRevenue = revenueRows.reduce((total, row) => total + row.amount, 0);
  const totalExpenses = expenseRows.reduce((total, row) => total + row.amount, 0);

  return {
    statement_type: "income_statement",
    period: {
      as_of: getTodayDate(),
    },
    sections: [
      { title: "Revenue", rows: revenueRows },
      { title: "Expenses", rows: expenseRows },
    ],
    totals: {
      total_revenue: totalRevenue,
      total_expenses: totalExpenses,
      net_income: totalRevenue - totalExpenses,
    },
  };
}

function buildTrialBalanceFromLedger(entries: LedgerEntry[]): StatementsResponse {
  const balances = computeBalances(entries);
  const rows = balances
    .filter((balance) => balance.balance !== 0)
    .map((balance) => ({
      label: `${balance.account_code} ${balance.account_name}`,
      debit: balance.balance > 0 ? Math.abs(balance.balance) : 0,
      credit: balance.balance < 0 ? Math.abs(balance.balance) : 0,
      amount: Math.abs(balance.balance),
    }));
  const totalDebits = rows.reduce((total, row) => total + (row.debit ?? 0), 0);
  const totalCredits = rows.reduce((total, row) => total + (row.credit ?? 0), 0);

  return {
    statement_type: "trial_balance",
    period: {
      as_of: getTodayDate(),
    },
    sections: [{ title: "Trial Balance", rows }],
    totals: {
      total_debits: totalDebits,
      total_credits: totalCredits,
    },
  };
}

function buildStatementsFromLedger(entries: LedgerEntry[], statementType: StatementType = "balance_sheet"): StatementsResponse {
  if (statementType === "income_statement") {
    return buildIncomeStatementFromLedger(entries);
  }
  if (statementType === "trial_balance") {
    return buildTrialBalanceFromLedger(entries);
  }
  return buildBalanceSheetFromLedger(entries);
}

function queueClarification(sourceText: string, response: ParseResponse) {
  const clarificationId = nextClarificationId();

  clarificationsStore = [
    {
      clarification_id: clarificationId,
      status: "pending",
      source_text: sourceText,
      explanation: response.explanation,
      confidence: {
        overall: response.confidence.overall,
      },
      proposed_entry: {
        lines: structuredClone(response.proposed_entry.lines),
      },
    },
    ...clarificationsStore,
  ];

  scheduleRealtimeUpdate({
    type: "clarification.created",
    parse_id: response.parse_id,
    occurred_at: new Date().toISOString(),
  });

  return clarificationId;
}

function postJournalEntry(
  parseId: string | undefined,
  description: string,
  lines: LedgerEntry["lines"],
  eventType: RealtimeEvent["type"] = "entry.posted",
) {
  const journalEntryId = nextJournalEntryId();
  const occurredAt = getCurrentTimestamp();

  ledgerEntriesStore = [
    {
      journal_entry_id: journalEntryId,
      date: getTodayDate(),
      occurred_at: occurredAt,
      description,
      status: "posted",
      lines: structuredClone(lines),
    },
    ...ledgerEntriesStore,
  ];

  scheduleRealtimeUpdate({
    type: eventType,
    journal_entry_id: journalEntryId,
    parse_id: parseId,
    occurred_at: occurredAt,
  });

  return journalEntryId;
}

export const mockApi = {
  async parseTransaction(input: ParseRequest): Promise<ParseAccepted> {
    await delay();

    const normalized = input.input_text.toLowerCase();
    if (normalized.includes("transfer")) {
      const response = structuredClone(parseNeedsClarificationFixture) as ParseResponse;
      const parseId = nextParseId();
      response.parse_id = parseId;
      response.proposed_entry.journal_entry_id = null;
      response.clarification_id = queueClarification(input.input_text, response);
      return {
        parse_id: parseId,
        status: "accepted",
      };
    }

    const response = structuredClone(parseAutoPostedFixture) as ParseResponse;
    const parseId = nextParseId();
    response.parse_id = parseId;
    response.proposed_entry.journal_entry_id = postJournalEntry(
      parseId,
      input.input_text,
      response.proposed_entry.lines,
    );
    return {
      parse_id: parseId,
      status: "accepted",
    };
  },

  async uploadTransactionFile(
    file: File,
    _options?: Pick<ParseRequest, "stages" | "store" | "post_stages">,
  ): Promise<ParseAccepted> {
    await delay();

    const source = deriveUploadSource(file);
    const lowerName = file.name.toLowerCase();
    const fileText = typeof file.text === "function" ? (await file.text()).toLowerCase() : lowerName;
    const needsClarification =
      fileText.includes("transfer") || lowerName.includes("transfer");
    const response = structuredClone(
      needsClarification ? parseNeedsClarificationFixture : parseAutoPostedFixture,
    ) as ParseResponse;

    const parseId = `upload_${file.name.replace(/[^a-z0-9]/gi, "_").toLowerCase()}`;
    response.parse_id = parseId;
    if (source === "pdf_upload") {
      response.explanation = `Imported ${file.name} through the PDF intake path and normalized the extracted text into the standard parsing flow.`;
    } else {
      response.explanation = needsClarification
        ? `Imported ${file.name} and flagged at least one transaction for clarification review.`
        : `Imported ${file.name} and staged the transactions for automatic posting review.`;
    }

    if (needsClarification) {
      response.proposed_entry.journal_entry_id = null;
      response.clarification_id = queueClarification(`Uploaded file: ${file.name}`, response);
      return {
        parse_id: parseId,
        status: "accepted",
      };
    }

    response.proposed_entry.journal_entry_id = postJournalEntry(
      parseId,
      `Imported transaction file: ${file.name}`,
      response.proposed_entry.lines,
    );
    response.clarification_id = null;
    return {
      parse_id: parseId,
      status: "accepted",
    };
  },

  async getClarifications(): Promise<ClarificationsResponse> {
    await delay(250);
    return {
      items: structuredClone(clarificationsStore),
      count: clarificationsStore.length,
    };
  },

  async resolveClarification(
    clarificationId: string,
    input: ResolveClarificationRequest,
  ): Promise<ResolveClarificationResponse> {
    await delay();

    const currentItem = clarificationsStore.find((item) => item.clarification_id === clarificationId) ?? null;
    clarificationsStore = clarificationsStore.filter((item) => item.clarification_id !== clarificationId);

    if (input.action === "approve" || input.action === "edit") {
      const currentLines = currentItem?.proposed_entry?.lines;
      const journalEntryId = postJournalEntry(
        currentItem?.clarification_id,
        currentItem?.source_text ?? "Clarified transfer posting",
        input.edited_entry?.lines ??
          currentLines ??
          (structuredClone(parseNeedsClarificationFixture.proposed_entry.lines) as LedgerEntry["lines"]),
        "clarification.resolved",
      );

      return {
        ...(structuredClone(clarificationResolvedFixture) as ResolveClarificationResponse),
        clarification_id: clarificationId,
        journal_entry_id: journalEntryId,
      };
    }

    scheduleRealtimeUpdate({
      type: "clarification.resolved",
      occurred_at: new Date().toISOString(),
    });

    return {
      clarification_id: clarificationId,
      status: "rejected",
    };
  },

  async getLedger(): Promise<LedgerResponse> {
    await delay(250);
    return {
      entries: structuredClone(ledgerEntriesStore),
      balances: computeBalances(ledgerEntriesStore),
      summary: computeLedgerSummary(ledgerEntriesStore),
    };
  },

  async getStatements(statementType?: StatementType, _asOf?: string): Promise<StatementsResponse> {
    await delay(250);
    return buildStatementsFromLedger(ledgerEntriesStore, statementType ?? "balance_sheet");
  },
};
