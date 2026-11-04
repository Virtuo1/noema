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

describe("Noema Frontend Epistemic & Interaction Guarantees", () => {
  it("renders the chat-first workspace by default with direct #command support and navigation", () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [],
        nodes: [],
        edges: [],
        counts: { nodes: 0, edges: 0, omitted_nodes: 0, omitted_edges: 0 },
        providers: [],
        remote_transfer_active: false,
      }),
    } as Response);

    renderWithQueryClient();

    expect(screen.getByText("Noema")).toBeDefined();
    expect(screen.getByText("Chat Workspace (Primary)")).toBeDefined();
    expect(screen.getByLabelText("Message or #command input")).toBeDefined();

    // Navigate to Timeline and return to Chat
    fireEvent.click(screen.getByText(/Timeline/));
    expect(
      screen.getByText("Knowledge Timeline & Revision Ledger"),
    ).toBeDefined();
    fireEvent.click(screen.getByText("← Return to Conversation"));
    expect(screen.getByLabelText("Message or #command input")).toBeDefined();
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
});
