import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import { ClarificationPage } from "./ClarificationPage";
import * as clarificationsApi from "../api/clarifications";

vi.mock("../api/realtime", () => ({
  subscribeToRealtimeUpdates: () => () => undefined,
}));

function renderClarificationPage() {
  return render(
    <MemoryRouter>
      <ClarificationPage />
    </MemoryRouter>,
  );
}

describe("clarification realtime header", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("shows the queue clock alongside the pending count", async () => {
    renderClarificationPage();

    expect(await screen.findByRole("heading", { name: /clarifications/i })).toBeInTheDocument();
    expect(await screen.findByText(/2 pending/i)).toBeInTheDocument();
    expect(screen.getByText(/queue synced/i)).toBeInTheDocument();
  });

  test("lets the reviewer edit journal lines before posting", async () => {
    renderClarificationPage();

    const codeInput = await screen.findByLabelText(/account code 1/i);
    fireEvent.change(codeInput, { target: { value: "1100" } });

    expect(screen.getByRole("button", { name: /save changes & post/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset draft/i })).toBeEnabled();
  });

  test("disables approval when no proposed entry was generated", async () => {
    vi.spyOn(clarificationsApi, "getClarifications").mockResolvedValue({
      count: 1,
      items: [
        {
          clarification_id: "cl-no-entry",
          status: "pending",
          source_text: "Transferred money",
          explanation: "Clarification required before a journal entry can be built.",
          confidence: { overall: 0.12 },
          proposed_entry: null,
        },
      ],
    });

    renderClarificationPage();

    expect(await screen.findByText(/build the debit and credit lines manually/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve & post/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /reject/i })).toBeEnabled();
  });

  test("allows creating manual lines and approving when no proposed entry exists", async () => {
    const resolveClarification = vi
      .spyOn(clarificationsApi, "resolveClarification")
      .mockResolvedValue({ clarification_id: "cl-no-entry", status: "resolved" });
    vi.spyOn(clarificationsApi, "getClarifications")
      .mockResolvedValueOnce({
        count: 1,
        items: [
          {
            clarification_id: "cl-no-entry",
            status: "pending",
            source_text: "Transferred money",
            explanation: "Clarification required before a journal entry can be built.",
            confidence: { overall: 0.12 },
            proposed_entry: null,
          },
        ],
      })
      .mockResolvedValueOnce({ count: 0, items: [] });

    renderClarificationPage();

    const codeInputOne = await screen.findByLabelText(/account code 1/i);
    const accountInputOne = screen.getByLabelText(/account name 1/i);
    const amountInputOne = screen.getByLabelText(/amount 1/i);
    const codeInputTwo = screen.getByLabelText(/account code 2/i);
    const accountInputTwo = screen.getByLabelText(/account name 2/i);
    const amountInputTwo = screen.getByLabelText(/amount 2/i);

    fireEvent.change(codeInputOne, { target: { value: "1500" } });
    fireEvent.change(accountInputOne, { target: { value: "Equipment" } });
    fireEvent.change(amountInputOne, { target: { value: "100" } });
    fireEvent.change(codeInputTwo, { target: { value: "1000" } });
    fireEvent.change(accountInputTwo, { target: { value: "Cash" } });
    fireEvent.change(amountInputTwo, { target: { value: "100" } });

    const approveButton = screen.getByRole("button", { name: /save changes & post/i });
    expect(approveButton).toBeEnabled();

    fireEvent.click(approveButton);

    expect(resolveClarification).toHaveBeenCalledWith("cl-no-entry", {
      action: "edit",
      edited_entry: {
        lines: [
          { account_code: "1500", account_name: "Equipment", type: "debit", amount: 100 },
          { account_code: "1000", account_name: "Cash", type: "credit", amount: 100 },
        ],
      },
    });
  });
});
