import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Noema App shell", () => {
  it("renders the application title", () => {
    render(<App />);
    expect(screen.getByText("Noema")).toBeDefined();
  });
});
