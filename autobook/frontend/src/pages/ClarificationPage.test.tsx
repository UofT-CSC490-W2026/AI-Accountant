import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ClarificationPage } from "./ClarificationPage";

function renderClarificationPage() {
  return render(
    <MemoryRouter>
      <ClarificationPage />
    </MemoryRouter>,
  );
}

describe("clarification realtime header", () => {
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
});
