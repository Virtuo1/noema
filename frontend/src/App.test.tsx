import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import {
  formatDemonstrationLabel,
  formatLayerBadge,
  formatSelfAssessmentLabel,
} from "./components/GraphView";

function renderWithQueryClient() {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("Noema Full-Screen Graph & Seamless Chat Workspace", () => {
  it("renders the full-screen graph by default, shows colored #tag autocomplete, and supports Esc universal back button", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [],
        nodes: [],
        edges: [],
        counts: { nodes: 0, edges: 0, omitted_nodes: 0, omitted_edges: 0 },
        conversation_provider: "google_gemini",
        conversation_model: "gemini-3-flash-preview",
        extraction_provider: "google_gemini",
        extraction_model: "gemini-3.5-flash-lite",
        providers: [],
      }),
    } as Response);

    renderWithQueryClient();

    expect(screen.getByText("Noema")).toBeDefined();
    expect(screen.getByLabelText("Knowledge graph surface")).toBeDefined();

    const input = screen.getByLabelText(
      "Message or #command input",
    ) as HTMLInputElement;
    expect(input).toBeDefined();

    // Typing # triggers the floating tag suggestion popup
    fireEvent.change(input, { target: { value: "Backpropagation #ah" } });
    expect(
      screen.getByRole("listbox", { name: "Tag suggestions" }),
    ).toBeDefined();
    expect(screen.getByText("#aha")).toBeDefined();

    // Clicking a tag suggestion completes it inline
    fireEvent.click(screen.getByText("#aha"));
    expect(input.value).toBe("Backpropagation #aha ");

    // Seamlessly switch to Chat view via top-middle toggle
    fireEvent.click(screen.getByText("💬 Chat"));
    expect(screen.getByLabelText("Chat surface")).toBeDefined();

    // Pressing Esc acts as the universal back button and transitions back into Graph overview
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByLabelText("Knowledge graph surface")).toBeDefined();
  });

  it("formats personal signals honestly without claiming objective mastery and distinguishes edge layers", () => {
    expect(
      formatSelfAssessmentLabel({
        encountered: true,
        explored: true,
        first_encountered_at: "2026-11-04T10:00:00Z",
        last_explored_at: "2026-11-04T10:05:00Z",
        self_assessment: "self_reports_understanding",
        demonstration_status: "none",
      }),
    ).toBe("You marked as aha (self-reported)");

    expect(
      formatDemonstrationLabel({
        encountered: true,
        explored: true,
        first_encountered_at: "2026-11-04T10:00:00Z",
        last_explored_at: "2026-11-04T10:05:00Z",
        self_assessment: "unknown",
        demonstration_status: "none",
      }),
    ).toBe("No confirmed demonstration yet");

    const userBadge = formatLayerBadge("user_established");
    const suggestedBadge = formatLayerBadge("suggested");
    const worldBadge = formatLayerBadge("world");

    expect(userBadge.label).toContain("User-established");
    expect(suggestedBadge.label).toContain("Suggested by AI (pending");
    expect(worldBadge.label).toContain("World claim (provisional");
  });

  it("renders the application with query client and allows interaction", () => {
    const { container } = renderWithQueryClient();
    expect(container).toBeDefined();
  });
});
