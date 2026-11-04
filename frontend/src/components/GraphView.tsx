/** Obsidian-style hierarchical & semantic-zoom knowledge graph with hover pop-out card. */

import React, { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type {
  ConceptSignalsDTO,
  GraphEdgeDTO,
  GraphNodeDTO,
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

const CATEGORY_PALETTE = [
  "#818cf8", // Indigo
  "#34d399", // Emerald
  "#38bdf8", // Sky
  "#fbbf24", // Amber
  "#c084fc", // Violet
  "#fb7185", // Rose
  "#2dd4bf", // Teal
  "#f472b6", // Pink
];

function getCategoryColorMap(nodes: GraphNodeDTO[]): Record<string, string> {
  const categories = Array.from(
    new Set(nodes.map((n) => n.category || "General")),
  ).sort();
  const map: Record<string, string> = {};
  categories.forEach((cat, idx) => {
    map[cat] = CATEGORY_PALETTE[idx % CATEGORY_PALETTE.length]!;
  });
  return map;
}

interface HoveredNodePopup {
  node: GraphNodeDTO;
  color: string;
  x: number;
  y: number;
}

interface GraphViewProps {
  graph: GraphProjectionResponse | undefined;
  isLoading: boolean;
  selectedConceptId: string | null;
  onSelectConcept: (conceptId: string) => void;
  onOpenConversation?: (conversationId: string) => void;
}

export const GraphView: React.FC<GraphViewProps> = ({
  graph,
  isLoading,
  selectedConceptId,
  onSelectConcept,
  onOpenConversation,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [hoveredPopup, setHoveredPopup] = useState<HoveredNodePopup | null>(
    null,
  );
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<
    string | null
  >(null);

  const nodes = useMemo(() => graph?.nodes ?? [], [graph]);
  const edges = useMemo(() => graph?.edges ?? [], [graph]);

  const categoryColorMap = useMemo(() => getCategoryColorMap(nodes), [nodes]);
  const categories = useMemo(
    () => Object.keys(categoryColorMap),
    [categoryColorMap],
  );

  // Build hierarchical clustered positions so concepts in the same topic group cluster together
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !graph || nodes.length === 0) return;

    let cy: cytoscape.Core | null = null;
    try {
      const visibleNodes = activeCategoryFilter
        ? nodes.filter(
            (n) => (n.category || "General") === activeCategoryFilter,
          )
        : nodes;
      const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));

      // Group nodes by category for deterministic hierarchical constellation layout
      const byCategory = new Map<string, GraphNodeDTO[]>();
      for (const n of visibleNodes) {
        const cat = n.category || "General";
        const list = byCategory.get(cat) ?? [];
        list.push(n);
        byCategory.set(cat, list);
      }

      const catKeys = Array.from(byCategory.keys());
      const numCats = Math.max(1, catKeys.length);
      const clusterRadius = numCats === 1 ? 0 : Math.max(220, numCats * 95);

      const positions: Record<string, { x: number; y: number }> = {};
      const hubById = new Map<string, string>();

      catKeys.forEach((cat, catIdx) => {
        const group = (byCategory.get(cat) ?? []).slice().sort((a, b) => {
          const lvlDiff = (a.hierarchy_level ?? 2) - (b.hierarchy_level ?? 2);
          if (lvlDiff !== 0) return lvlDiff;
          return (b.importance ?? 1) - (a.importance ?? 1);
        });

        const angle = (2 * Math.PI * catIdx) / numCats - Math.PI / 2;
        const centerX = numCats === 1 ? 0 : Math.cos(angle) * clusterRadius;
        const centerY = numCats === 1 ? 0 : Math.sin(angle) * clusterRadius;

        const hubNode = group[0];
        if (!hubNode) return;
        positions[hubNode.id] = { x: centerX, y: centerY };

        const subNodes = group.slice(1);
        subNodes.forEach((sub, idx) => {
          hubById.set(sub.id, hubNode.id);
          const lvl = sub.hierarchy_level ?? 2;
          const ringRadius =
            lvl === 1
              ? 75
              : lvl === 2
                ? 115 + (idx % 3) * 28
                : 175 + (idx % 4) * 25;
          const subAngle =
            (2 * Math.PI * idx) / Math.max(1, subNodes.length) + catIdx * 0.45;
          positions[sub.id] = {
            x: centerX + Math.cos(subAngle) * ringRadius,
            y: centerY + Math.sin(subAngle) * ringRadius,
          };
        });
      });

      // Explicit edges between visible nodes + implicit category hub tethers so clusters stay cohesive
      const explicitEdges = edges.filter(
        (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
      );
      const connectedPairs = new Set<string>();
      for (const e of explicitEdges) {
        connectedPairs.add(`${e.source}::${e.target}`);
        connectedPairs.add(`${e.target}::${e.source}`);
      }

      const syntheticClusterEdges: cytoscape.ElementDefinition[] = [];
      for (const [subId, hubId] of hubById.entries()) {
        const hasAnyConnectionInCluster = explicitEdges.some(
          (e) => e.source === subId || e.target === subId,
        );
        if (
          !hasAnyConnectionInCluster &&
          !connectedPairs.has(`${subId}::${hubId}`)
        ) {
          syntheticClusterEdges.push({
            data: {
              id: `cluster-${hubId}-${subId}`,
              source: hubId,
              target: subId,
              isHierarchy: true,
              isImplicitCluster: true,
            },
          });
        }
      }

      const elements: cytoscape.ElementDefinition[] = [
        ...visibleNodes.map((node) => {
          const cat = node.category || "General";
          const color = categoryColorMap[cat] || "#818cf8";
          const level = node.hierarchy_level ?? 2;
          const baseSize = level === 1 ? 26 : level === 2 ? 16 : 10;
          const mentionBoost = Math.min(10, (node.mention_count ?? 1) * 1.8);
          return {
            data: {
              id: node.id,
              label: node.label,
              category: cat,
              color,
              hierarchyLevel: level,
              size: Math.round(baseSize + mentionBoost),
            },
            position: positions[node.id] ?? { x: 0, y: 0 },
          };
        }),
        ...explicitEdges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            isHierarchy: edge.is_hierarchy,
            isImplicitCluster: false,
          },
        })),
        ...syntheticClusterEdges,
      ];

      cy = cytoscape({
        container: el,
        elements,
        minZoom: 0.35,
        maxZoom: 3.0,
        wheelSensitivity: 0.25,
        style: [
          {
            selector: "node",
            style: {
              "background-color": "data(color)",
              "background-opacity": 0.9,
              width: "data(size)",
              height: "data(size)",
              "border-width": 1.5,
              "border-color": "#ffffff",
              "border-opacity": 0.2,
              label: "",
              color: "#f4f4f5",
              "font-size": 11,
              "font-family":
                "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              "text-valign": "bottom",
              "text-halign": "center",
              "text-margin-y": 6,
              "text-outline-width": 3,
              "text-outline-color": "#000000",
              "transition-property":
                "width, height, border-width, border-opacity, opacity",
              "transition-duration": 140,
            },
          },
          // Semantic zoom label classes
          {
            selector: "node.show-label",
            style: {
              label: "data(label)",
            },
          },
          {
            selector: "node[hierarchyLevel = 1]",
            style: {
              "font-size": 13,
              "font-weight": "bold",
              "border-width": 2.5,
              "border-opacity": 0.45,
            },
          },
          {
            selector: "node.hovered",
            style: {
              label: "data(label)",
              "border-width": 3,
              "border-color": "#ffffff",
              "border-opacity": 1,
              "font-size": 13,
              "font-weight": "bold",
              color: "#ffffff",
              "z-index": 999,
            },
          },
          {
            selector: "node.neighbor",
            style: {
              label: "data(label)",
              "border-opacity": 0.75,
              opacity: 1,
            },
          },
          {
            selector: "node.dimmed",
            style: {
              opacity: 0.16,
              label: "",
            },
          },
          {
            selector: "node:selected",
            style: {
              label: "data(label)",
              "border-width": 3,
              "border-color": "#ffffff",
              "border-opacity": 1,
            },
          },
          {
            selector: "edge",
            style: {
              width: 1.1,
              "line-color": "#52525b",
              opacity: 0.28,
              "curve-style": "bezier",
              // Never render edge text labels (Obsidian style)
              label: "",
            },
          },
          {
            selector: "edge[?isHierarchy]",
            style: {
              width: 1.4,
              "line-color": "#71717a",
              opacity: 0.35,
            },
          },
          {
            selector: "edge[?isImplicitCluster]",
            style: {
              width: 0.8,
              "line-style": "dotted",
              "line-color": "#3f3f46",
              opacity: 0.2,
            },
          },
          {
            selector: "edge.highlighted",
            style: {
              width: 2,
              "line-color": "#e4e4e7",
              opacity: 0.85,
              "z-index": 99,
            },
          },
          {
            selector: "edge.dimmed",
            style: {
              opacity: 0.05,
            },
          },
        ],
        layout: {
          name: "preset",
          fit: true,
          padding: 90,
        },
      });

      cyRef.current = cy;

      // Apply semantic zoom visibility rules based on current zoom factor
      const applySemanticZoom = () => {
        if (!cy) return;
        const z = cy.zoom();
        setZoomLevel(Number(z.toFixed(2)));
        cy.batch(() => {
          cy!.nodes().forEach((n) => {
            const lvl = Number(n.data("hierarchyLevel") ?? 2);
            if (z < 0.85) {
              // Zoomed out: simplify to major topic hubs only
              if (lvl === 1) {
                n.addClass("show-label");
              } else {
                n.removeClass("show-label");
              }
            } else if (z < 1.35) {
              // Normal zoom: show hubs and core concepts, hide leaf labels
              if (lvl <= 2) {
                n.addClass("show-label");
              } else {
                n.removeClass("show-label");
              }
            } else {
              // Zoomed in: reveal all detail labels
              n.addClass("show-label");
            }
          });
        });
      };

      applySemanticZoom();
      cy.on("zoom", applySemanticZoom);

      const nodeById = new Map(visibleNodes.map((n) => [n.id, n]));

      // Hover pop-out + floating source card
      cy.on("mouseover", "node", (evt) => {
        if (!cy) return;
        const targetNode = evt.target;
        const id = String(targetNode.id());
        const dto = nodeById.get(id);
        const neighborhood = targetNode.closedNeighborhood();

        cy.batch(() => {
          cy!.elements().addClass("dimmed");
          neighborhood.removeClass("dimmed");
          neighborhood.nodes().addClass("neighbor");
          neighborhood.edges().addClass("highlighted");
          targetNode.removeClass("neighbor").addClass("hovered");
        });

        if (dto) {
          const renderedPos = targetNode.renderedPosition();
          setHoveredPopup({
            node: dto,
            color: String(targetNode.data("color") || "#818cf8"),
            x: renderedPos.x,
            y: renderedPos.y,
          });
        }
      });

      cy.on("mouseout", "node", () => {
        if (!cy) return;
        cy.batch(() => {
          cy!.elements().removeClass("dimmed hovered neighbor highlighted");
        });
        setHoveredPopup(null);
      });

      cy.on("tap", "node", (evt) => {
        const id = String(evt.target.id());
        onSelectConcept(id);
      });

      if (selectedConceptId) {
        cy.$id(selectedConceptId).select();
      }
    } catch {
      // Headless / jsdom fallback
    }

    return () => {
      if (cy) {
        cy.destroy();
        cyRef.current = null;
      }
    };
  }, [
    graph,
    nodes,
    edges,
    categoryColorMap,
    activeCategoryFilter,
    selectedConceptId,
    onSelectConcept,
  ]);

  const handleZoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: {
        x: cy.width() / 2,
        y: cy.height() / 2,
      },
    });
  };

  const handleResetZoom = () => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.fit(undefined, 90);
  };

  const semanticZoomDescription =
    zoomLevel < 0.85
      ? "Macro topics"
      : zoomLevel < 1.35
        ? "Core topics"
        : "Detailed concepts";

  return (
    <section
      aria-label="Knowledge graph surface"
      className="relative w-screen h-screen bg-black overflow-hidden select-none"
    >
      {/* Subtle radial dot background */}
      <div
        className="absolute inset-0 pointer-events-none opacity-25"
        style={{
          backgroundImage:
            "radial-gradient(circle at center, rgba(255,255,255,0.16) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />

      {/* Full-screen Cytoscape Canvas */}
      <div
        ref={containerRef}
        data-testid="cytoscape-canvas"
        className="w-full h-full"
      />

      {/* Empty State Overlay */}
      {!isLoading && nodes.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-6 text-center">
          <div className="max-w-md rounded-3xl bg-black/60 backdrop-blur-xl border border-white/10 p-8 shadow-2xl">
            <div className="w-3 h-3 rounded-full bg-white mx-auto mb-4 shadow-[0_0_20px_rgba(255,255,255,0.9)]" />
            <h2 className="text-lg font-medium text-white tracking-tight">
              Your knowledge graph is ready
            </h2>
            <p className="mt-2 text-xs text-zinc-400 leading-relaxed">
              Ask a question in the box below to begin. As you chat and tag
              moments with <span className="text-zinc-200 font-mono">#aha</span>{" "}
              or <span className="text-zinc-200 font-mono">#important</span>,
              Noema automatically organizes and groups your topics here.
            </p>
          </div>
        </div>
      )}

      {/* Top-Right Floating Topic Group Filter & Semantic Zoom Controls */}
      {nodes.length > 0 && (
        <div className="fixed top-5 right-5 z-20 flex flex-col items-end gap-2 max-w-md">
          {/* Topic Group Color Pills */}
          <div className="flex flex-wrap justify-end gap-1.5 rounded-2xl bg-black/70 backdrop-blur-2xl border border-white/10 px-3 py-2 shadow-xl">
            <button
              type="button"
              onClick={() => setActiveCategoryFilter(null)}
              className={`text-[11px] px-2 py-0.5 rounded-lg transition-colors ${
                activeCategoryFilter === null
                  ? "bg-white text-black font-medium"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              All topics
            </button>
            {categories.map((cat) => {
              const color = categoryColorMap[cat];
              const isSelected = activeCategoryFilter === cat;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() =>
                    setActiveCategoryFilter(isSelected ? null : cat)
                  }
                  className={`flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded-lg transition-colors ${
                    isSelected
                      ? "bg-white/20 text-white font-medium border border-white/30"
                      : "text-zinc-300 hover:bg-white/10"
                  }`}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="truncate max-w-[130px]">{cat}</span>
                </button>
              );
            })}
          </div>

          {/* Semantic Zoom Indicator & Controls */}
          <div className="flex items-center gap-1.5 rounded-xl bg-black/70 backdrop-blur-2xl border border-white/10 px-2.5 py-1 text-[11px] text-zinc-400 shadow-xl">
            <span>{semanticZoomDescription}</span>
            <span className="text-zinc-600">·</span>
            <button
              type="button"
              onClick={() => handleZoomBy(0.8)}
              title="Zoom out to broader topics"
              className="px-1.5 py-0.5 rounded hover:bg-white/10 text-zinc-300"
            >
              −
            </button>
            <button
              type="button"
              onClick={handleResetZoom}
              title="Reset view"
              className="px-1.5 py-0.5 rounded hover:bg-white/10 text-zinc-300"
            >
              Fit
            </button>
            <button
              type="button"
              onClick={() => handleZoomBy(1.25)}
              title="Zoom in for sub-topic details"
              className="px-1.5 py-0.5 rounded hover:bg-white/10 text-zinc-300"
            >
              +
            </button>
          </div>
        </div>
      )}

      {/* Hover Pop-Out Card over the hovered node */}
      {hoveredPopup && (
        <div
          data-testid="graph-hover-card"
          style={{
            left: Math.min(
              Math.max(24, hoveredPopup.x + 18),
              typeof window !== "undefined" ? window.innerWidth - 340 : 600,
            ),
            top: Math.min(
              Math.max(24, hoveredPopup.y - 24),
              typeof window !== "undefined" ? window.innerHeight - 220 : 400,
            ),
          }}
          className="fixed z-40 w-80 pointer-events-none rounded-2xl bg-black/85 backdrop-blur-2xl border border-white/20 p-4 shadow-[0_20px_50px_rgba(0,0,0,0.9)] animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-zinc-300">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: hoveredPopup.color }}
              />
              {hoveredPopup.node.category || "General"}
            </span>
            <span className="text-[10px] text-zinc-500">
              {hoveredPopup.node.mention_count} mention
              {hoveredPopup.node.mention_count === 1 ? "" : "s"}
            </span>
          </div>

          <h3 className="mt-1 text-sm font-semibold text-white">
            {hoveredPopup.node.label}
          </h3>

          {hoveredPopup.node.tags && hoveredPopup.node.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {hoveredPopup.node.tags.map((t) => (
                <span
                  key={t}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-white border border-white/15"
                >
                  #{t}
                </span>
              ))}
            </div>
          )}

          {hoveredPopup.node.top_quote && (
            <p className="mt-2 text-xs text-zinc-300 line-clamp-3 italic border-l-2 border-white/20 pl-2.5">
              “{hoveredPopup.node.top_quote}”
            </p>
          )}

          <div className="mt-3 pt-2 border-t border-white/10 flex items-center justify-between text-[11px] text-zinc-400">
            <span className="truncate">
              Saved in:{" "}
              <strong className="text-zinc-200 font-medium">
                {hoveredPopup.node.source_conversation_title ||
                  "Knowledge base"}
              </strong>
            </span>
            {onOpenConversation && hoveredPopup.node.source_conversation_id && (
              <span className="text-zinc-500 shrink-0 ml-2">
                Click to inspect
              </span>
            )}
          </div>
        </div>
      )}

      {/* Accessible semantic fallback list for screen readers / tests */}
      <div className="sr-only" aria-label="Graph nodes list">
        {nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onSelectConcept(node.id)}
          >
            {node.label} ({node.category || "General"})
          </button>
        ))}
      </div>
    </section>
  );
};
