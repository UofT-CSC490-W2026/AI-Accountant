import clarificationResolvedFixture from "./fixtures/clarification-resolved.json";
import clarificationsPendingFixture from "./fixtures/clarifications-pending.json";
import ledgerFixture from "./fixtures/ledger-sample.json";
import parseNeedsClarificationFixture from "./fixtures/parse-needs-clarification.json";
import statementsFixture from "./fixtures/statements-sample.json";
import type {
  ClarificationItem,
  ClarificationsResponse,
  LedgerEntry,
  LedgerResponse,
  ParseAccepted,
  ParseRequest,
  ResolveClarificationRequest,
  ResolveClarificationResponse,
  StatementsResponse
} from "../api/types";
import { emitMockEvent } from "../api/realtime";

let clarificationsStore: ClarificationItem[] = structuredClone(
  clarificationsPendingFixture.items
) as ClarificationItem[];

let ledgerEntriesStore: LedgerEntry[] = structuredClone(ledgerFixture.entries) as LedgerEntry[];

function delay(ms = 350) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
    total_credits: totalCredits
  };
}

function computeBalances(entries: LedgerEntry[]): LedgerResponse["balances"] {
  const balanceMap = new Map<string, { account_code: string; account_name: string; balance: number }>();

  for (const entry of entries) {
    for (const line of entry.lines) {
      const current = balanceMap.get(line.account_code) ?? {
        account_code: line.account_code,
        account_name: line.account_name,
        balance: 0
      };

      current.balance += line.type === "debit" ? line.amount : -line.amount;
      balanceMap.set(line.account_code, current);
    }
  }

  return Array.from(balanceMap.values()).sort((left, right) =>
    left.account_code.localeCompare(right.account_code)
  );
}

export const mockApi = {
  async parseTransaction(input: ParseRequest): Promise<ParseAccepted> {
    await delay();

    const parseId = `parse_mock_${Date.now()}`;
    const normalized = input.input_text.toLowerCase();
    const needsClarification = normalized.includes("transfer");

    // Simulate async pipeline: emit event after a short delay
    setTimeout(() => {
      if (needsClarification) {
        emitMockEvent({
          type: "clarification.created",
          journal_entry_id: "",
          occurred_at: new Date().toISOString(),
        });
      } else {
        emitMockEvent({
          type: "entry.posted",
          journal_entry_id: `je_mock_${Date.now()}`,
          occurred_at: new Date().toISOString(),
        });
      }
    }, 500);

    return { parse_id: parseId, status: "accepted" };
  },

  async uploadTransactionFile(file: File): Promise<ParseAccepted> {
    await delay();

    const parseId = `upload_${file.name.replace(/[^a-z0-9]/gi, "_").toLowerCase()}`;

    // Simulate async pipeline: emit event after a short delay
    setTimeout(() => {
      emitMockEvent({
        type: "entry.posted",
        journal_entry_id: `je_mock_${Date.now()}`,
        occurred_at: new Date().toISOString(),
      });
    }, 500);

    return { parse_id: parseId, status: "accepted" };
  },

  async getClarifications(): Promise<ClarificationsResponse> {
    await delay(250);
    return {
      items: structuredClone(clarificationsStore),
      count: clarificationsStore.length
    };
  },

  async resolveClarification(
    clarificationId: string,
    input: ResolveClarificationRequest
  ): Promise<ResolveClarificationResponse> {
    await delay();

    clarificationsStore = clarificationsStore.filter(
      (item) => item.clarification_id !== clarificationId
    );

    if (input.action === "approve" || input.action === "edit") {
      ledgerEntriesStore = [
        ...ledgerEntriesStore,
        {
          journal_entry_id: clarificationResolvedFixture.journal_entry_id,
          date: "2026-03-17",
          description: "Clarified transfer posting",
          status: "posted",
          lines:
            input.edited_entry?.lines ??
            (structuredClone(parseNeedsClarificationFixture.proposed_entry.lines) as LedgerEntry["lines"])
        }
      ];

      emitMockEvent({
        type: "clarification.resolved",
        journal_entry_id: clarificationResolvedFixture.journal_entry_id,
        occurred_at: new Date().toISOString(),
      });

      return structuredClone(clarificationResolvedFixture) as ResolveClarificationResponse;
    }

    emitMockEvent({
      type: "clarification.resolved",
      journal_entry_id: "",
      occurred_at: new Date().toISOString(),
    });

    return {
      clarification_id: clarificationId,
      status: "rejected"
    };
  },

  async getLedger(): Promise<LedgerResponse> {
    await delay(250);
    return {
      entries: structuredClone(ledgerEntriesStore),
      balances: computeBalances(ledgerEntriesStore),
      summary: computeLedgerSummary(ledgerEntriesStore)
    };
  },

  async getStatements(): Promise<StatementsResponse> {
    await delay(250);
    return structuredClone(statementsFixture) as StatementsResponse;
  }
};
