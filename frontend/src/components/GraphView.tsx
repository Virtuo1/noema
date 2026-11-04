/** Clean, low-cognitive-load Knowledge Map with toggleable Map vs List view. */

import React, { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type {
  ConceptSignalsDTO,
  GraphEdgeDTO,
  GraphProjectionResponse,
} from "../api/types";

export function formatSelfAssessmentLabel(signals: ConceptSignalsDTO): string {
  switch (signals.self_assessment) {
    case "self_reports_understanding":
      return "You marked as aha (self-reported)";
    case "confused":
      return "You marked as confused";
    case "uncertain":
      return "Open question / uncertain";
    default:
      return signals.explored ? "Explored in conversation" : "Encountered";
  }
}

export function formatDemonstrationLabel(signals: ConceptSignalsDTO): string {
  switch (signals.demonstration_status) {
    case "repeated_evidence":
      return "Shown across multiple explanations";
    case "some_evidence":
      return "Shown in your explanation";
    case "contradictory_evidence":
      return "Revised / conflicting evidence";
    default:
      return "No confirmed demonstration yet";
  }
}

export function formatLayerBadge(layer: GraphEdgeDTO["layer"]): {
  label: string;
  styleText: string;
  className: string;
} {
  if (layer === "user_established") {
    return {
      label: "User-established (solid)",
      styleText: "Solid line",
      className: "bg-emerald-950/80 text-emerald-300 border-emerald-700",
    };
  }
  if (layer === "suggested") {
    return {
      label: "Suggested by AI (pending, dashed)",
      styleText: "Dashed line",
      className: "bg-amber-950/80 text-amber-300 border-amber-700",
    };
  }
  return {
    label: "World claim (provisional, dotted)",
    styleText: "Dotted line",
    className: "bg-sky-950/80 text-sky-300 border-sky-700",
  };
}

interface GraphViewProps {
  graph: GraphProjectionResponse | undefined;
  isLoading: boolean;
  selectedConceptId: string | null;
  onSelectConcept: (conceptId: string) => void;
  activeLayers: string[];
  onToggleLayer: (layer: string) => void;
  asOfTimestamp: string;
  onChangeAsOf: (value: string) => void;
  onReturnToChat: () => void;
  onAcceptSuggestion: (suggestionId: string) => void;
  onRejectSuggestion: (suggestionId: string) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({
  graph,
  isLoading,
  selectedConceptId,
  onSelectConcept,
  activeLayers,
  onToggleLayer,
  onReturnToChat,
  onAcceptSuggestion,
  onRejectSuggestion,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewMode, setViewMode] = useState<"map" | "list">("map");

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !graph || viewMode !== "map") return;

    let cy: cytoscape.Core | null = null;
    try {
      const elements: cytoscape.ElementDefinition[] = [
        ...graph.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label,
            selfAssessment: node.signals.self_assessment,
          },
        })),
        ...graph.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.predicate_label,
            layer: edge.layer,
          },
        })),
      ];

      cy = cytoscape({
        container: el,
        elements,
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              color: "#f4f4f5",
              "background-color": "#27272a",
              "border-width": 2,
              "border-color": "#71717a",
              "font-size": "12px",
              "text-valign": "bottom",
              "text-margin-y": 7,
              width: 32,
              height: 32,
            },
          },
          {
            selector: 'node[selfAssessment = "self_reports_understanding"]',
            style: {
              "border-width": 3,
              "border-color": "#34d399",
              "background-color": "#064e3b",
            },
          },
          {
            selector: 'node[selfAssessment = "confused"]',
            style: {
              "border-width": 3,
              "border-color": "#fbbf24",
              "background-color": "#451a03",
            },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "curve-style": "bezier",
              "target-arrow-shape": "triangle",
              label: "data(label)",
              "font-size": "10px",
              color: "#a1a1aa",
              "text-background-color": "#09090b",
              "text-background-opacity": 0.85,
              "text-background-padding": "2px",
            },
          },
          {
            selector: 'edge[layer = "user_established"]',
            style: {
              "line-style": "solid",
              "line-color": "#10b981",
              "target-arrow-color": "#10b981",
              width: 2.5,
            },
          },
          {
            selector: 'edge[layer = "suggested"]',
            style: {
              "line-style": "dashed",
              "line-color": "#f59e0b",
              "target-arrow-color": "#f59e0b",
            },
          },
          {
            selector: 'edge[layer = "world"]',
            style: {
              "line-style": "dotted",
              "line-color": "#38bdf8",
              "target-arrow-color": "#38bdf8",
            },
          },
        ],
        layout: {
          name: "cose",
          animate: false,
          padding: 48,
        },
      });

      cy.on("tap", "node", (evt) => {
        const nodeId = evt.target.id();
        if (nodeId) {
          onSelectConcept(String(nodeId));
        }
      });
    } catch {
      // Headless or jsdom environments without full canvas measurements safely fall back.
    }

    return () => {
      if (cy) {
        cy.destroy();
      }
    };
  }, [graph, onSelectConcept, viewMode]);

  return (
    <section
      aria-label="Personal Knowledge Graph Projection"
      className="max-w-5xl mx-auto py-6 px-4 space-y-4"
    >
      {/* Clean Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Knowledge Map</h2>
          <p className="text-xs text-zinc-400">
            Click any concept to see where it came from in your chats.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Layer Filters */}
          {(
            [
              { id: "user", label: "My Links" },
              { id: "world", label: "Domain Facts" },
              { id: "suggested", label: "Suggested" },
            ] as const
          ).map((layer) => {
            const active = activeLayers.includes(layer.id);
            return (
              <button
                key={layer.id}
                type="button"
                aria-pressed={active}
                onClick={() => onToggleLayer(layer.id)}
                className={`px-2.5 py-1 rounded-full border transition ${
                  active
                    ? "bg-zinc-800 text-zinc-100 border-zinc-600"
                    : "bg-zinc-950 text-zinc-500 border-zinc-800"
                }`}
              >
                {active ? "✓ " : ""}
                {layer.label}
              </button>
            );
          })}

          <div className="h-4 w-px bg-zinc-800 mx-1" />

          {/* View Mode Toggle */}
          <div className="inline-flex rounded-lg bg-zinc-900 border border-zinc-800 p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("map")}
              className={`px-2.5 py-1 rounded-md transition ${
                viewMode === "map"
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Map
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`px-2.5 py-1 rounded-md transition ${
                viewMode === "list"
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              List ({graph?.counts.nodes ?? 0})
            </button>
          </div>

          <button
            type="button"
            onClick={onReturnToChat}
            className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium"
          >
            ← Back to Chat
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-sm text-zinc-400 p-8 text-center">
          Loading knowledge map...
        </div>
      )}

      {graph && graph.nodes.length === 0 && (
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-12 text-center space-y-2">
          <p className="text-sm font-medium text-zinc-200">
            Your map is empty right now
          </p>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            Just chat naturally in the conversation tab—concepts and connections
            are organized automatically in the background.
          </p>
        </div>
      )}

      {graph && graph.nodes.length > 0 && viewMode === "map" && (
        <div className="space-y-3">
          <div
            ref={containerRef}
            data-testid="cytoscape-canvas"
            className="w-full h-[65vh] rounded-xl border border-zinc-800/90 bg-zinc-950"
          />
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400 px-1">
            <div className="flex flex-wrap items-center gap-4">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 bg-emerald-400 inline-block" /> My
                connection (solid)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 border-b border-dotted border-sky-400 inline-block" />{" "}
                Domain fact (dotted)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 border-b border-dashed border-amber-400 inline-block" />{" "}
                Suggested link (dashed)
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {graph.nodes.slice(0, 8).map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => onSelectConcept(n.id)}
                  className={`px-2 py-0.5 rounded-full border transition ${
                    selectedConceptId === n.id
                      ? "bg-indigo-950 border-indigo-500 text-indigo-200"
                      : "bg-zinc-900 border-zinc-800 text-zinc-300 hover:border-zinc-700"
                  }`}
                >
                  {n.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {graph && graph.nodes.length > 0 && viewMode === "list" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-2.5">
            <h3 className="text-xs font-medium text-zinc-400">
              Concepts ({graph.counts.nodes})
            </h3>
            <ul className="space-y-2">
              {graph.nodes.map((node) => (
                <li
                  key={node.id}
                  className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/80 flex items-center justify-between gap-2"
                >
                  <div>
                    <div className="text-sm font-medium text-zinc-100">
                      {node.label}
                    </div>
                    <div className="text-[11px] text-zinc-400">
                      {formatSelfAssessmentLabel(node.signals)}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSelectConcept(node.id)}
                    className="px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200"
                  >
                    Open
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-2.5">
            <h3 className="text-xs font-medium text-zinc-400">
              Connections ({graph.counts.edges})
            </h3>
            <ul className="space-y-2">
              {graph.edges.map((edge) => {
                const badge = formatLayerBadge(edge.layer);
                const sourceLabel =
                  graph.nodes.find((n) => n.id === edge.source)?.label ||
                  edge.source;
                const targetLabel =
                  graph.nodes.find((n) => n.id === edge.target)?.label ||
                  edge.target;
                return (
                  <li
                    key={edge.id}
                    className="p-2.5 rounded-lg bg-zinc-950/70 border border-zinc-800/80 space-y-1.5 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-200">
                        {sourceLabel}{" "}
                        <span className="text-zinc-400">
                          → {edge.predicate_label} →
                        </span>{" "}
                        {targetLabel}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded border ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </div>
                    {edge.layer === "suggested" && edge.suggestion_id && (
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() =>
                            onAcceptSuggestion(edge.suggestion_id!)
                          }
                          className="px-2 py-0.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white"
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            onRejectSuggestion(edge.suggestion_id!)
                          }
                          className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-300"
                        >
                          Ignore
                        </button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
};
