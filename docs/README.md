# Noema product and architecture foundation

This directory is the working product and technical specification for the LLM-native personal knowledge environment. It is written to guide an initial implementation and to make assumptions and unresolved choices visible. It does not prescribe application code or claim that proposed AI-derived knowledge is objectively true.

## Documents

1. [Product specification](product-spec.md) — users, interaction, requirements, scope, and open decisions.
2. [System architecture](architecture.md) — components, boundaries, flows, deployment, and provider integration.
3. [Data model](data-model.md) — entities, relationships, constraints, schema proposal, and a worked example.
4. [Knowledge and understanding model](knowledge-model.md) — what the system may infer about the user's knowledge and how it represents uncertainty.
5. [Graph and visualization](graph-and-visualization.md) — graph projection, semantic zoom, interaction, and rendering recommendation.
6. [Retrieval and AI pipeline](retrieval-and-ai.md) — indexing, hybrid retrieval, context construction, extraction, and failure handling.
7. [API design](api.md) — implementation-independent initial HTTP API.
8. [Decisions and roadmap](decisions-and-roadmap.md) — ADRs, trade-offs, phases, and validation gates.

## Baseline assumptions

- **Initial deployment:** a single user runs the web application locally. The browser UI talks to a local FastAPI service. There is no account service, multi-user tenancy, cloud sync, or collaboration in the first prototype.
- **Data control:** the local database is the source of truth. Hosted model calls are opt-in per provider/model configuration; local inference is supported through the same adapter boundary. The UI must communicate when content is sent to a remote provider.
- **Database:** SQLite is recommended for this local single-user starting point, with FTS5 for lexical search and exact vector ranking in the application for the first small corpus. This avoids requiring a database server or extension at install time. The schema keeps vector operations behind a repository interface so PostgreSQL plus pgvector remains a credible deployment choice if sync, multiple writers, or measured search scale justifies it.
- **Graph semantics:** a graph edge is never, by itself, evidence that the user understands the relationship. World-model claims, user-established connections, and AI suggestions are separate records.
- **History:** current state is a query-friendly projection; append-only knowledge events preserve how that state changed. This is intentionally not full event sourcing.
- **AI confidence:** model confidence is a review hint, not a calibrated probability and never a substitute for user evidence.

## Status and change policy

These documents are a proposed baseline, not immutable requirements. Requirements from the brief are marked **Core**; design choices made to make the proposal implementable are marked **Recommendation** or **Assumption**. Items requiring a product decision are collected in the product specification. When implementation changes an architectural decision, update its ADR and the dependent schema/API documents in the same change.

The terms **must**, **should**, and **may** are used in their ordinary requirements sense: must = required for the initial workflow, should = recommended unless a documented reason says otherwise, may = optional or future capability.
