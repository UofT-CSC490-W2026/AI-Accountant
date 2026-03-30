import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { resetMockApiState } from "../mocks/mockApi";

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof window !== "undefined" && !window.ResizeObserver) {
  window.ResizeObserver = MockResizeObserver as typeof ResizeObserver;
}

beforeEach(() => {
  resetMockApiState();
});
