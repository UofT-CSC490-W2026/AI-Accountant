import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { resetMockApiState } from "../mocks/mockApi";

beforeEach(() => {
  resetMockApiState();
});
