# Graph architecture and visualization

## 1. The graph is a view of records, not the knowledge database

The relational model remains authoritative. A graph response is a bounded projection containing node/edge IDs, labels, semantic kind, status, evidence counts, timestamps, and source links. The frontend may compute layout coordinates and transient clusters, but it does not invent or persist semantic facts as graph edges.

The projection combines visibly distinct layers:

- **Concept nodes:** stable concept identities.
- **Hierarchy edges:** world claims with typed predicates such as `is_a`, `part_of`, or `prerequisite_for`; source and claim status remain available.
- **World-claim edges:** sourced relationships about the domain, styled by provisional/supported/challenged status.
- **User-established edges:** direct user assertions, explicit connection annotations, or accepted suggestions.
- **Suggested edges:** pending AI discoveries, shown separately and optionally hidden by default.
- **Evidence links:** a user opens a node/edge to see messages, annotations, and other sources; evidence links need not all be drawn as graph edges.

The same pair of concepts can have a world relation and a personal relation with separate provenance. Never coalesce these into a single unlabeled line.

## 2. Hierarchy, arbitrary links, and clusters

Use two complementary structures:

1. **Typed hierarchy:** explicit semantic relationships (e.g. “neural network is a kind of machine learning model,” “chain rule is part of calculus”). These support drill-down and breadcrumbs when evidence is strong enough. A provisional world claim can inform a suggested grouping but should not silently define a permanent hierarchy.
2. **Arbitrary cross-connections:** typed or user-described relations such as analogy, contrast, dependency, cause, or a personal association. These remain independent of hierarchy and can link distant domains.

For a broad overview, produce clusters from the currently selected nodes using hierarchy first and graph clustering/semantic similarity as optional supporting signals. Generated clusters are a layout/aggregation aid, not user knowledge. Use versioned ephemeral cluster IDs and labels, or cached projections that can be rebuilt. If users later create their own named areas, model them as explicit personal collections rather than mutating concept identity.

This hybrid avoids forcing every concept into one tree and avoids rendering a flat hairball. A concept can be located in a hierarchy and participate in many cross-domain relations.

## 3. Semantic zoom

Zoom changes both scale and information density:

| Level | Display | Interactions |
|---|---|---|
| Overview | Large domain clusters, counts, recent activity, unresolved questions, and perhaps a few important user-established connections | Click cluster to expand; filter by domain, time, status, or evidence |
| Domain | Subdomains and selected high-signal concepts; suggestions shown as a separate overlay | Expand/collapse a branch; open a concept; reveal cross-links on demand |
| Concept neighborhood | Selected concept, hierarchy path, a bounded number of directly related concepts, edge labels/status, and activity cues | Follow edge, open evidence, start a grounded chat |
| Evidence detail | Exact message/annotation excerpts, source date, origin, extraction status, and relation history | Jump to full conversation, accept/reject suggestion, correct relation |

Use semantic thresholds based on both viewport scale and graph size, but avoid hard-coded zoom levels as the only rule. The API should return a view appropriate to an explicit focus and budget; the client chooses visual density within that result.

## 4. Layout and graph API projection

Start with a deterministic hierarchical/compound layout for `is_a`/`part_of` subgraphs and a force-directed layout for a focused neighborhood with cross-links. Avoid continuously moving nodes after the user has started exploring. Preserve positions in client view state for a session; optional per-user layout pins may be added later, separate from knowledge data.

Graph query inputs should include:

- `focus_concept_id` or overview mode;
- `depth`/`limit` and node/edge budgets;
- included relation layers (`world`, `user`, `suggested`);
- relation predicates and confidence/status filters;
- time `as_of` for history;
- search text or selected concept IDs;
- whether hierarchy/cluster summaries are requested.

The response should include `truncated`, counts omitted, and expansion cursors or a next neighborhood action. It should not return an unbounded whole-workspace graph by default.

Example edge view model:

```json
{
  "id": "user-relation:ur_9",
  "source": "c_bp",
  "target": "c_hb",
  "predicate": "contrasts_with_learning",
  "layer": "user_established",
  "status": "active",
  "origin": "accepted_suggestion",
  "evidence_count": 2,
  "created_at": "2026-11-04T10:15:00Z"
}
```

A pending suggestion returns `layer: "suggested"`, `status: "pending"`, plus the explanation and evidence IDs. It is never returned with `layer: "user_established"` before acceptance.

## 5. Visual encoding

Use redundant visual cues so meaning is not color-only:

- solid labeled edge: user-established relation;
- dashed edge and “suggested” badge: pending AI relation;
- dotted or muted edge: provisional world claim;
- explicit status icon/text for challenged or superseded claim;
- node ring/icon for explicit self-report, not a generic “mastered” green fill;
- small evidence/activity marks for recent exploration or demonstrated evidence;
- distinct interaction for hierarchy vs cross-links.

Provide a legend and keyboard-accessible list/outline alternative. Tooltips alone are insufficient for provenance or relation meaning.

## 6. Filtering and history

Filters should include relation layer, predicate, suggestion status, explicit/inferred signals, evidence type, and time range. Default view should favor user-established relations and selected hierarchy; pending suggestions belong in a toggle or side panel to reduce clutter.

Historical graph mode asks the backend for a projection as of a timestamp. It should visually indicate the selected date and show changes from the present when useful. It must rebuild state from the event history or version records, not merely hide newer nodes while keeping newer relation statuses.

## 7. Scale strategy

Personal graph size is unknown, so defer claims about a universal node limit. Control complexity by:

- focused neighborhood queries and node/edge budgets;
- aggregation of hierarchy and generated clusters at overview level;
- hiding lower-priority AI suggestions by default;
- keeping labels and evidence details off the canvas until focus/zoom;
- debouncing layout and search work;
- using a Web Worker for expensive client-side clustering/layout if measured;
- monitoring frame time and interaction latency on realistic synthetic graphs.

If a focused view grows beyond what Cytoscape renders smoothly in target browsers, first improve projection/filtering and layout. If the product requires dense, very large canvas rendering, evaluate a WebGL renderer such as Sigma.js behind the same graph view adapter. The visualization library must not dictate relation semantics or database shape.

## 8. Library recommendation

**Start with Cytoscape.js.** It is a browser graph visualization and analysis library with selectors, events, layouts, serialization, and graph algorithms; it can also run headlessly. This fits a moderate, interactive concept neighborhood and lets the team focus on meaning, evidence access, and semantic zoom before custom rendering. Its official documentation describes the library and its graph/layout/selector capabilities. [Cytoscape.js](https://js.cytoscape.org/)

Keep the integration behind a small React adapter that accepts the graph DTO and emits concept/relation selection events. Do not let Cytoscape element data become a duplicate source of truth. If measurements later show that the target graphs exceed its performance envelope, compare Sigma.js or a custom WebGL layer with the same API projection.
