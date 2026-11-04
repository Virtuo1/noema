/** Bounded knowledge graph projection view with Cytoscape.js adapter and accessible list outline. */

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
  asOfTimestamp,
  onChangeAsOf,
  onReturnToChat,
  onAcceptSuggestion,
  onRejectSuggestion,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [viewMode, setViewMode] = useState<
    "canvas_and_outline" | "outline_only"
  >("canvas_and_outline");

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !graph || viewMode === "outline_only") return;

    let cy: cytoscape.Core | null = null;
    try {
      const elements: cytoscape.ElementDefinition[] = [
        ...graph.nodes.map((node) => ({
          data: {
            id: node.id,
            label: `${node.label}${
              node.signals.self_assessment === "self_reports_understanding"
                ? " [aha]"
                : node.signals.self_assessment === "confused"
                  ? " [confused]"
                  : ""
            }`,
            selfAssessment: node.signals.self_assessment,
          },
        })),
        ...graph.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: `${edge.predicate_label} (${
              edge.layer === "user_established"
                ? "yours"
                : edge.layer === "suggested"
                  ? "suggested"
                  : "world"
            })`,
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
              color: "#f1f5f9",
              "background-color": "#1e293b",
              "border-width": 2,
              "border-color": "#64748b",
              "font-size": "11px",
              "text-valign": "bottom",
              "text-margin-y": 6,
              width: 34,
              height: 34,
            },
          },
          {
            selector: 'node[selfAssessment = "self_reports_understanding"]',
            style: {
              "border-width": 4,
              "border-color": "#34d399",
            },
          },
          {
            selector: 'node[selfAssessment = "confused"]',
            style: {
              "border-width": 4,
              "border-color": "#fbbf24",
            },
          },
          {
            selector: "edge",
            style: {
              width: 2,
              "curve-style": "bezier",
              "target-arrow-shape": "triangle",
              label: "data(label)",
              "font-size": "9px",
              color: "#cbd5e1",
              "text-background-color": "#0f172a",
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
              width: 3,
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
          padding: 36,
        },
      });

      cy.on("tap", "node", (evt) => {
        const nodeId = evt.target.id();
        if (nodeId) {
          onSelectConcept(String(nodeId));
        }
      });
    } catch {
      // Headless or jsdom environments without full canvas measurements gracefully fall back to the accessible outline below.
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
      className="flex flex-col gap-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-lg p-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onReturnToChat}
            className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white"
          >
            ← Return to Conversation
          </button>
          <div>
            <h2 className="text-sm font-semibold text-slate-100">
              Knowledge Graph Projection
            </h2>
            <p className="text-xs text-slate-400">
              Separates user-established relations (solid), provisional world
              claims (dotted), and pending AI suggestions (dashed).
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {(
            [
              { id: "user", label: "Your Relations (Solid)" },
              { id: "world", label: "World Claims (Dotted)" },
              { id: "suggested", label: "AI Suggestions (Dashed)" },
            ] as const
          ).map((layer) => {
            const active = activeLayers.includes(layer.id);
            return (
              <button
                key={layer.id}
                type="button"
                aria-pressed={active}
                onClick={() => onToggleLayer(layer.id)}
                className={`px-2.5 py-1 rounded border ${
                  active
                    ? "bg-slate-800 text-slate-100 border-slate-500"
                    : "bg-slate-950 text-slate-500 border-slate-800"
                }`}
              >
                {active ? "✓ " : ""}
                {layer.label}
              </button>
            );
          })}

          <label className="flex items-center gap-1.5 text-slate-300 ml-2">
            <span>Historical as-of:</span>
            <input
              type="text"
              placeholder="YYYY-MM-DDTHH:MM:SSZ"
              value={asOfTimestamp}
              onChange={(e) => onChangeAsOf(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 w-44"
            />
          </label>

          <button
            type="button"
            onClick={() =>
              setViewMode((m) =>
                m === "canvas_and_outline"
                  ? "outline_only"
                  : "canvas_and_outline",
              )
            }
            className="px-2.5 py-1 rounded border border-slate-700 bg-slate-950 text-slate-300"
          >
            {viewMode === "canvas_and_outline"
              ? "Accessible Outline Only"
              : "Show Graph Canvas"}
          </button>
        </div>
      </div>

      {isLoading && (
        <div className="text-xs text-slate-400 p-4">
          Loading graph projection...
        </div>
      )}

      {graph && (
        <>
          {viewMode === "canvas_and_outline" && (
            <div
              ref={containerRef}
              data-testid="cytoscape-canvas"
              className="w-full h-80 rounded-lg border border-slate-800 bg-slate-950"
            />
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Accessible Concept Nodes List */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Concepts ({graph.counts.nodes})
              </h3>
              {graph.nodes.length === 0 ? (
                <p className="text-xs text-slate-400">
                  No concepts extracted yet. Explore an idea in chat first.
                </p>
              ) : (
                <ul className="space-y-2">
                  {graph.nodes.map((node) => {
                    const isSelected = selectedConceptId === node.id;
                    return (
                      <li
                        key={node.id}
                        className={`p-2.5 rounded border flex items-center justify-between gap-2 ${
                          isSelected
                            ? "border-indigo-500 bg-indigo-950/30"
                            : "border-slate-800 bg-slate-950/60"
                        }`}
                      >
                        <div>
                          <div className="text-sm font-medium text-slate-100">
                            {node.label}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5 flex flex-wrap gap-2">
                            <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200">
                              {formatSelfAssessmentLabel(node.signals)}
                            </span>
                            <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
                              {formatDemonstrationLabel(node.signals)}
                            </span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => onSelectConcept(node.id)}
                          className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 shrink-0"
                        >
                          Inspect Evidence
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Accessible Relationships & Pending Suggestions List */}
            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Relationships & Suggestions ({graph.counts.edges})
              </h3>
              {graph.edges.length === 0 ? (
                <p className="text-xs text-slate-400">
                  No relationships in selected layers.
                </p>
              ) : (
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
                        className="p-2.5 rounded border border-slate-800 bg-slate-950/60 space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-100">
                            {sourceLabel}{" "}
                            <span className="text-indigo-300">
                              —[{edge.predicate_label}]→
                            </span>{" "}
                            {targetLabel}
                          </span>
                          <span
                            className={`text-[11px] px-2 py-0.5 rounded border ${badge.className}`}
                          >
                            {badge.label}
                          </span>
                        </div>
                        {edge.explanation && (
                          <p className="text-xs text-slate-400">
                            {edge.explanation}
                          </p>
                        )}
                        {edge.layer === "suggested" && edge.suggestion_id && (
                          <div className="flex items-center gap-2 pt-1">
                            <button
                              type="button"
                              onClick={() =>
                                onAcceptSuggestion(edge.suggestion_id!)
                              }
                              className="px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-xs text-white"
                            >
                              Accept into Personal Map
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                onRejectSuggestion(edge.suggestion_id!)
                              }
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
};
