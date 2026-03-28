import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { TransactionPage } from "./TransactionPage";

const {
  getParseStatus,
  parseTransaction,
  uploadTransactionFile,
  subscribeToRealtimeUpdates,
  waitForRealtimeConnection,
} = vi.hoisted(() => ({
  getParseStatus: vi.fn(),
  parseTransaction: vi.fn(),
  uploadTransactionFile: vi.fn(),
  subscribeToRealtimeUpdates: vi.fn(),
  waitForRealtimeConnection: vi.fn(),
}));

vi.mock("../api/parse", () => ({
  getParseStatus,
  parseTransaction,
  uploadTransactionFile,
}));

vi.mock("../api/realtime", () => ({
  subscribeToRealtimeUpdates,
  waitForRealtimeConnection,
}));

function renderTransactionPage() {
  return render(
    <MemoryRouter>
      <TransactionPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.stubEnv("VITE_USE_MOCK_API", "false");
  parseTransaction.mockReset();
  uploadTransactionFile.mockReset();
  getParseStatus.mockReset();
  subscribeToRealtimeUpdates.mockReset();
  waitForRealtimeConnection.mockReset();
  subscribeToRealtimeUpdates.mockReturnValue(() => {});
  waitForRealtimeConnection.mockResolvedValue(undefined);
  getParseStatus.mockResolvedValue({
    parse_id: "parse_live_default",
    status: "processing",
    occurred_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("transaction page live realtime flow", () => {
  test("waits for the realtime connection before submitting parse requests", async () => {
    let releaseConnection = () => {};
    waitForRealtimeConnection.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          releaseConnection = resolve;
        }),
    );
    parseTransaction.mockResolvedValue({ parse_id: "parse_live_1" });

    renderTransactionPage();
    fireEvent.click(screen.getByRole("button", { name: /parse transaction/i }));

    expect(waitForRealtimeConnection).toHaveBeenCalledTimes(1);
    expect(parseTransaction).not.toHaveBeenCalled();

    releaseConnection();

    await waitFor(() => {
      expect(parseTransaction).toHaveBeenCalledWith({
        input_text: "Bought a laptop for $2400",
        source: "manual_text",
        currency: "CAD",
      });
    });
  });

  test("ignores unrelated realtime events and waits for the matching parse result", async () => {
    let listener: ((event: { type: string; parse_id?: string; occurred_at: string; status?: string }) => void) | undefined;
    subscribeToRealtimeUpdates.mockImplementation((nextListener) => {
      listener = nextListener;
      return () => {};
    });
    parseTransaction.mockResolvedValue({ parse_id: "parse_live_2" });

    renderTransactionPage();
    fireEvent.click(screen.getByRole("button", { name: /parse transaction/i }));

    expect(await screen.findByText(/transaction accepted \(id: parse_live_2\)/i)).toBeInTheDocument();
    expect(listener).toBeDefined();

    await act(async () => {
      listener?.({
        type: "entry.posted",
        parse_id: "different_parse_id",
        occurred_at: new Date().toISOString(),
        status: "auto_posted",
      });
    });

    expect(screen.getByRole("heading", { name: /processing/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /entry posted/i })).not.toBeInTheDocument();

    await act(async () => {
      listener?.({
        type: "entry.posted",
        parse_id: "parse_live_2",
        occurred_at: new Date().toISOString(),
        status: "auto_posted",
      });
    });

    expect(await screen.findByRole("heading", { name: /entry posted/i })).toBeInTheDocument();
  });

  test("recovers through parse status polling when realtime completion is missed", async () => {
    sessionStorage.setItem("autobook_pending_parse_id", "parse_live_3");
    getParseStatus.mockResolvedValue({
      parse_id: "parse_live_3",
      status: "auto_posted",
      occurred_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      explanation: "Posted from polling fallback",
      proposed_entry: {
        journal_entry_id: "je_123",
        lines: [],
      },
    });

    renderTransactionPage();

    expect(await screen.findByRole("heading", { name: /entry posted/i })).toBeInTheDocument();
    expect(getParseStatus).toHaveBeenCalledWith("parse_live_3");
  });
});
