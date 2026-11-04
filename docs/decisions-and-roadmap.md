# Architecture decisions and development roadmap

This document contains ADRs for the local single-user architecture. Decisions marked “Accepted” are implemented in the repository and can be revised when a product decision changes. Each ADR records alternatives and the trigger for review.

## ADR-001: Start with SQLite for a local single-user prototype

**Status:** Accepted  
**Decision:** Use SQLite as the local source of truth, WAL mode, foreign keys enabled on every connection, short write transactions, FTS5 for lexical search, and application-side exact vector ranking for an initially small corpus.

### Context

The first implementation is assumed to be a web UI served against one local user's data. Requiring a PostgreSQL service, credentials, and deployment configuration would add install and operational work without an initial multi-user requirement. The product needs relational integrity, event history, local export, full-text search, and background writes. It does not yet have a vector volume that justifies approximate indexing.

SQLite permits multiple simultaneous readers but only one simultaneous write transaction; WAL improves reader/writer coexistence but does not remove the single-writer constraint. Keep the worker to one writer-oriented loop, keep write transactions short, and never hold them over model calls. [SQLite transactions](https://sqlite.org/lang_transaction.html), [SQLite WAL](https://sqlite.org/wal.html)

### Alternatives

| Option | Benefits | Costs / why not now |
|---|---|---|
| PostgreSQL from day one | Strong multi-user concurrency, operational tooling, FTS and relational querying in one server, pgvector option | Requires a running service and backup/upgrade story for local desktop use; greater operational setup for a single local user. |
| SQLite plus vector extension now | Local file, embedded nearest-neighbor index | Native extension compatibility/packaging and extension maintenance add risk. Exact search is adequate until measured otherwise. |
| Separate vector database | Dedicated vector search capabilities | Another process, backup and consistency boundary; unnecessary at personal scale. |

### Consequences

- The local database file is easy to back up and own, but a corrupt/lost file remains a user-data risk; export and backup UX matter.
- SQLite migrations and FTS triggers need explicit care. Foreign key enforcement is connection-configured and must be verified at startup. [SQLite foreign keys](https://www.sqlite.org/foreignkeys.html)
- An eventual PostgreSQL move is a real migration. Preserve stable IDs, use portable relational concepts, export rows through a database adapter, and rebuild FTS/vector indexes. Do not claim Alembic makes all SQL portable.
- Use SQLite JSON text for flexible event payloads, but validate at application boundaries. SQLite stores JSON as ordinary text; PostgreSQL `jsonb` has different behavior and indexing. [SQLite JSON](https://sqlite.org/json1.html), [PostgreSQL JSON types](https://www.postgresql.org/docs/current/datatype-json.html)

### Review when

Choose PostgreSQL before launch if the initial product must be remotely hosted, multi-user, synchronized across devices, or support concurrent workers with material write volume. Also review after profiling shows exact vector search or write serialization violates measured response/throughput targets.

## ADR-002: Local-first deployment is the initial product boundary

**Status:** Accepted  
**Decision:** Run the browser UI and API locally; persist data on the user's device; call hosted AI providers only when selected/configured. No cloud sync or authentication is in the prototype.

### Alternatives and trade-offs

- **Hosted-first:** simpler access from multiple devices and centralized updates, but requires account/auth, server-side data security, trust/compliance, and a hosted database before those needs are validated.
- **Local-first with sync:** strong ownership/offline use but requires conflict semantics, device identity, encryption, sync protocol, and merge UX. SQLite is not a sync design.
- **Local-only without hosted models:** strongest isolation but constrains model quality/availability on user hardware. This remains a selectable configuration, not the only mode.

The selected approach fits data ownership and local model support. It also accepts a single-device limitation. Provider settings should make remote transfer explicit. When hosted multi-device use is chosen, design auth, encryption in transit/at rest, account deletion, tenant isolation, backups, and a sync/conflict model as a separate architecture decision.

## ADR-003: Store the graph in relational tables

**Status:** Accepted  
**Decision:** Use relational concept, claim, personal relation, suggestion, evidence, and event tables. Implement graph traversal as indexed SQL joins with a bounded depth.

### Alternatives and trade-offs

- **Dedicated graph database:** expressive path queries and graph algorithms; adds a service/backup boundary and may complicate cross-record transactions with conversations and annotations.
- **Property graph as JSON:** flexible early, but weak foreign keys, provenance joins, and constraints; difficult to report or migrate.
- **Relational relations:** strong provenance, transactions, conventional tooling, straightforward export; deep, unbounded traversals become verbose and are not the initial workload.

The expected graph is personal and user-sized. Initial navigation is focused, one or two hops, and evidence-heavy. Revisit only if real workloads need complex path queries or graph algorithms that cannot be expressed acceptably in the relational model. Visualization remains a projection and cannot dictate storage.

## ADR-004: Separate exact vector ranking behind a retrieval port

**Status:** Accepted  
**Decision:** Store vectors with model/dimension metadata; use exact application-side ranking initially. Keep lexical and vector retrieval behind a common repository interface and evaluate recall/latency before indexing approximately.

### Alternatives and trade-offs

- **pgvector:** colocates vectors, metadata, and relational filters; supports exact search plus HNSW/IVFFlat approximate indexes and hybrid full-text approaches. It is a strong option for PostgreSQL hosting, but an extension adds deployment/version considerations and approximate indexes trade recall for speed. [pgvector](https://github.com/pgvector/pgvector)
- **Dedicated vector store:** useful for large/independently scaled corpora, but adds consistency and operational work.
- **Local SQLite vector extension:** may keep everything embedded, but package and runtime compatibility must be validated for target platforms before adopting it.

Use exact search as a baseline because it has predictable recall and avoids index tuning. Revisit when a representative benchmark shows latency or memory trouble. Evaluate candidate recall as well as speed before switching to ANN.

## ADR-005: Use a small provider abstraction, not a provider framework

**Status:** Accepted  
**Decision:** Define application-owned interfaces for chat completion/streaming, embeddings, and structured extraction. Implement adapters for the first hosted provider and an OpenAI-compatible local endpoint as needed. Store provider/model/prompt metadata per run.

### Alternatives and trade-offs

- **Direct provider SDK calls in domain code:** fastest first request, but makes provider changes, local inference, testing, and telemetry inconsistent.
- **Large unified LLM framework:** accelerates integrations and chains, but may impose abstractions/prompts and increase dependency surface beyond the initial needs.
- **Application-owned narrow interfaces:** modest initial adapter work and good task/provider control; new provider-specific features require deliberate capability support.

Keep a capability map for streaming, schema-constrained output, embeddings, and context window. Do not pretend all providers behave identically or require one model per job initially. Keys never go to the browser or normal logs.

## ADR-006: Use a durable SQLite-backed worker queue first

**Status:** Accepted  
**Decision:** Persist extraction/embedding jobs in the same database transaction as their source completion and process them with one restartable worker loop, leases, bounded retries, and idempotency keys.

### Alternatives and trade-offs

- **In-process fire-and-forget task:** minimal code but work is lost on process exit and retries/status are weak.
- **External broker and worker service:** robust independent scaling, but adds infrastructure and duplicate-delivery/operations considerations before volume requires it.
- **Database-backed queue:** durable and simple at local scale; SQLite single-writer behavior limits concurrency and the worker must avoid long transactions.

If the product moves to hosted multi-worker operation, move the same job contract to a queue/broker or PostgreSQL-backed queue as appropriate. Job semantics and idempotency remain stable.

## ADR-007: Keep current projections plus an append-only knowledge event ledger

**Status:** Accepted  
**Decision:** Store current state in relational projection tables and append a typed `knowledge_events` record for each meaningful change. Historical views replay those deltas. Do not event-source every message and setting.

### Alternatives and trade-offs

- **Mutable current rows only:** simplest reads, but loses how understanding or relation status changed.
- **Full event sourcing:** complete replay and audit, but raises complexity around schema evolution, projections, deletion, and every domain operation.
- **Projection plus scoped events:** simple current reads and meaningful temporal history; replay requires strict event payload/version discipline and privacy-aware deletion.

Messages are the original evidence. Knowledge events record state changes, not duplicate message bodies. Event payloads should be versioned and limited. User deletion may remove/redact related events when retaining them would violate data ownership.

## ADR-008: Use React/TypeScript with a graph-renderer adapter; start with Cytoscape.js

**Status:** Accepted  
**Decision:** Keep a React + TypeScript + Vite frontend, server state through TanStack Query, minimal local state, and a graph component adapter. Start with Cytoscape.js for an interactive bounded graph.

### Alternatives and trade-offs

- **Sigma.js/WebGL first:** potentially better for very large dense graph rendering; more investment in graph view interactions before scale need is known.
- **Custom canvas/WebGL:** full control but substantial rendering, accessibility, and interaction work.
- **Cytoscape.js:** graph selectors, layouts, events, and serializable elements fit an early concept neighborhood; validate performance with representative data and keep it replaceable. [Cytoscape.js](https://js.cytoscape.org/)

The graph DTO is owned by the API. Cytoscape-specific data and positions stay at the view layer. React and the API boundary also preserve a path to Tauri packaging without committing to desktop process/security details now.

## ADR-009: Use sourced claims for the world model and user-owned records for personal knowledge

**Status:** Accepted  
**Decision:** Persist world statements as provisional/supported/challenged claims with provenance. Store personal states and user relations separately. Store AI discoveries as pending suggestions. Promotion requires user evidence/action or a trustworthy source workflow appropriate to the claim.

### Alternatives and trade-offs

- **One shared graph with confidence labels:** less schema work, but users can easily confuse an AI fact or relation with their own knowledge.
- **AI output treated as verified world knowledge:** fast and fluent, but makes hallucinations indistinguishable from sourced claims.
- **Separate claim/user/suggestion layers:** more explicit records and slightly more UI work; preserves agency and makes provenance queryable.

This separation is a core product requirement, not an optimization to remove later.

## Development roadmap

The prototype is a vertical workflow with durable data and explicit provenance. It is not a complete knowledge platform.

### Phase 0 — Set product boundaries and data contracts

- Confirm local-first single-user assumption for the prototype and choose the first chat/embedding provider configuration.
- Establish API schemas, table migration baseline, event vocabulary, annotation UX, and relation predicates.
- Create a small synthetic/consented conversation set for retrieval and extraction review.

**Exit:** a developer can explain which records are source, world claim, personal state, user relation, and suggestion without ambiguity.

### Phase 1 — Core interactive prototype (first implementation milestone)

Implement only the central loop:

1. Create a conversation and exchange messages in chat.
2. Persist turns reliably with provider/model metadata.
3. Add a message annotation such as `#aha` through either a typed command or a direct UI action, with immediate feedback and undo.
4. Queue extraction asynchronously; extract concepts/mentions and typed candidates with evidence links.
5. Store world claims, user states, pending suggestions, and events separately.
6. Render a bounded concept graph with hierarchy/relations and an evidence side panel.
7. Accept/reject a suggested connection and show the resulting timeline event.
8. Retrieve one relevant prior passage in a later chat and expose its source.

**Exit:** the user can complete all six core workflow steps from the brief, and can tell at each point what is explicit, inferred, provisional, or accepted. No background failure loses a chat message.

### Phase 2 — Retrieval and provenance quality

- Add FTS and message chunking; add embeddings behind a provider adapter.
- Tune hybrid ranking and context budgets using the small evaluation set.
- Add concept evidence views, open questions, source citation UI, and correction/merge paths.
- Evaluate suggestions for relevance and user friction.

**Exit:** relevant prior material can be found reliably without overwhelming the assistant context or user interface.

### Phase 3 — Temporal and ownership quality

- Add historical graph `as_of` projection and richer event replay.
- Implement full export/delete semantics and backup/restore guidance.
- Improve job retries, status visibility, logs, provider-secret handling, accessibility, and privacy UX.
- Profile realistic graph and vector sizes; decide whether SQLite exact search remains adequate.

**Exit:** data can be backed up/exported, corrected/deleted, and historically inspected without misleading state.

### Phase 4 — Decide on hosted sync and desktop packaging

- Run a product decision on multi-device access, sync/conflicts, hosted accounts, and threat model.
- If hosted: adopt PostgreSQL and pgvector only if validated workload warrants it; build tenant isolation, authentication, backups, and operational monitoring.
- If desktop: test Tauri packaging, backend lifecycle, local key storage, upgrade/migration behavior, and offline provider choices.

**Exit:** choose one target architecture from measured use and explicit product needs rather than enabling both deployment paths speculatively.

## First milestone acceptance checklist

- A user can ask a question and continue the same conversation.
- The chat response does not wait for extraction.
- Conversation/model failures and extraction failures have separate visible statuses.
- Typed `#aha` or a UI annotation is anchored to a specific message/span, stays user-authored, and needs no confirmation dialog.
- Concepts and relations link to source messages and extraction provenance.
- A suggested Backpropagation–Hebbian connection remains visibly pending until a user action accepts it.
- Acceptance creates a user relation and event but does not mark Hebbian learning as understood.
- The graph opens concept evidence and differentiates world claims, user relations, and suggestions.
- A subsequent conversation retrieves a relevant prior message and can link to its source.
- The event view preserves revisions and does not present understanding as monotonically increasing.
