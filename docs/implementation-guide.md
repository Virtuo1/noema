# Contributor and coding-agent guide

This guide is for developers and AI coding agents working in the Noema repository. It translates the product foundation into day-to-day implementation practices. Antigravity and compatible agents load the root [`AGENTS.md`](../AGENTS.md) as persistent project guidance; this guide holds fuller implementation details. If this guide conflicts with the product specification or an accepted ADR, update the guide or raise the inconsistency; do not silently change product semantics. [Antigravity Rules documentation](https://antigravity.google/docs/rules/)

## Repository

- **GitHub:** [Virtuo1/noema](https://github.com/Virtuo1/noema)
- **Issues:** [GitHub Issues](https://github.com/Virtuo1/noema/issues)
- **Current state:** product/architecture documentation only; no application scaffold or established build commands are present yet.

The user authorizes coding agents to read and modify repository files and expects completed milestone work to be committed and pushed to `main`. Do not ask for routine approval to edit, commit, or push project work. Do not force-push or rewrite shared history. If an HTTPS push fails, try SSH authentication before concluding credentials are unavailable. If `main` is protected or no authorized push method works, keep work safely committed on a task branch and record the blocker in [`implementation-status.md`](implementation-status.md). Do not change repository settings or deploy without a separate request.

## Read these first

1. [Product and architecture index](README.md)
2. [Product specification](product-spec.md)
3. [Architecture](architecture.md)
4. [Data model](data-model.md)
5. [Knowledge model](knowledge-model.md)
6. [Roadmap and ADRs](decisions-and-roadmap.md)

Use the ADRs as the record of accepted technical choices. The baseline assumes a local, single-user prototype. Where a decision is marked proposed or left open, choose the smallest reversible option for the current milestone and record material changes in an ADR.

When the user asks to “implement the application,” treat the roadmap phases that deliver core product requirements as one continuing objective. Complete them incrementally; do not treat the prototype exit as completion. Future features and unresolved hosted/desktop deployment decisions remain deferred unless requested. Avoid stopping to ask about ordinary reversible choices: follow the documented defaults and record the choice.

## Resumable implementation

Keep [`implementation-status.md`](implementation-status.md) current as the durable handoff between sessions and agents. At session start, read it and inspect the actual Git state. After each coherent milestone, record what is done, what is in progress, the exact next action, open blockers/decisions, validation performed, and the commit on `main`. Before a potentially long or risky operation, record its active step. On resumption, reconcile the ledger with the repository, preserve partial work, and continue from the first incomplete acceptance criterion. Do not repeat completed work or rely on chat history as the project log.

Before calling a milestone complete, run the relevant checks already configured in the project, validate its acceptance criteria, fix any failures, and record exact commands/results in the status ledger. Never report a check as passed unless it was run.

## Working principles

- **Build the vertical slice first:** chat → keep/annotate an explanation → background concept linking → later contextual retrieval → optional graph/history inspection.
- **Keep chat friction low:** do not make users categorize each turn, clear a suggestion queue, or open the graph to get continuity.
- **Separate epistemic layers:** world claims, user states, user-established relations, and AI suggestions are different records and API states.
- **Keep source evidence reachable:** derived concepts, claims, signals, and relations must point back to source messages/spans and extraction provenance where applicable.
- **Treat user commands as explicit actions:** supported standalone `#commands` and UI actions produce the same annotation. Show immediate feedback and undo; do not add a confirmation dialog by default.
- **Keep suggestions optional:** an AI-discovered relation stays a suggestion until the user explicitly accepts it. A clear user-authored relation may be recorded as user-asserted with its source evidence.
- **Do not overstate understanding:** an `#aha` is a self-report. Saving an assistant response does not imply the user understands it. Repeated discussion is not mastery.
- **Preserve history:** revise knowledge through events and new evidence; do not silently overwrite prior beliefs or claims.
- **Prefer a modular monolith:** keep clear domain modules, but do not add services, queues, or databases without a demonstrated need.
- **Keep user data portable:** stable IDs, versioned migrations, source-first records, and documented export behavior.

## Code organization

When the application scaffold is introduced, keep dependencies pointed inward toward domain behavior:

- **Frontend:** React/TypeScript screens and interaction components call typed API clients. Keep graph renderer details behind a view adapter. Server state belongs in TanStack Query; add a separate global state store only when a real shared transient-state need appears.
- **API layer:** FastAPI routes validate HTTP input/output and delegate to domain services. Do not put knowledge rules in route handlers.
- **Domain modules:** conversations, knowledge, retrieval, graph projection, and AI integrations own their operations. Cross-module writes go through services, not ad hoc table updates.
- **Persistence:** SQLAlchemy models/repositories and Alembic migrations implement the relational contract. Enable SQLite foreign keys on every connection and use short transactions.
- **AI gateway:** provider SDKs stay inside adapters. Domain code uses application-owned request/response types and records provider/model/prompt provenance.
- **Background work:** persist jobs before processing; handlers must be idempotent and safe to retry. Never hold a database transaction open while waiting on a model or embedding service.

Do not introduce a graph database, vector service, message broker, authentication system, or multi-user tenancy in the local prototype without an explicit decision and evidence that the current design is insufficient.

## Code standards

These are project conventions to adopt when the relevant scaffold/tooling is added. Follow checked-in configuration over personal preferences.

### Tooling to establish with the application scaffold

The repository does not have implementation tooling yet. When scaffolding the application, commit reproducible dependency lockfiles and select/configure formatters and linters in-repo. Recommended starting point: Ruff for Python linting/formatting; ESLint and Prettier for TypeScript/React. Avoid relying on globally installed tools or undocumented editor defaults. Pin compatible versions in project manifests/lockfiles rather than this guide.

### Python

- Use type hints for public functions and domain/API boundaries.
- Follow PEP 8 naming: `snake_case` for functions, variables, and modules; `PascalCase` for classes.
- Keep functions and domain services focused; prefer explicit data structures over loosely shaped dictionaries except for validated event payloads.
- Validate external/provider output before it reaches domain writes. Use Pydantic at API and structured-model boundaries.
- Use SQLAlchemy 2-style APIs and Alembic migrations once the application scaffold selects versions.
- Keep provider-specific code out of domain and retrieval ranking rules.

### TypeScript and React

- Keep TypeScript strict; avoid `any`. If a boundary is genuinely unknown, use `unknown` and validate it.
- Use `camelCase` for values/functions, `PascalCase` for React components and types, and explicit names for API/domain concepts.
- Keep components accessible by keyboard and assistive technology. Do not encode statuses by color alone.
- Keep API DTOs separate from renderer-specific Cytoscape element data.
- Prefer generated API types from OpenAPI once the API contract exists; avoid maintaining duplicate handwritten schemas without a reason.

### Database and API

- Use application-generated stable UUIDs and UTC timestamps.
- Keep message source text immutable; model edits/revisions explicitly.
- Add migrations for schema changes; do not rely on `create_all` or manual edits to a developer database.
- Use relational constraints for ownership, uniqueness, enum checks, and foreign keys where practical; validate cross-table invariants in domain services.
- Return stable API error codes and avoid returning provider secrets, raw traces, or unrelated private message content.
- Version breaking API changes; keep persistence entities separate from response models.

## Privacy and security rules

- Bind local API listeners to loopback by default; never expose an unauthenticated local service on the network.
- Do not put API keys or tokens in source control, frontend bundles, ordinary database fields, screenshots, or logs.
- Redact secrets and avoid logging conversation text by default.
- Keep remote model use visible and send only selected context for the requested task.
- Treat imported text, retrieved messages, and model output as untrusted data; validate, delimit, and escape it.
- When deleting source content, remove dependent search documents, embeddings, evidence, and derived personal records according to the product deletion policy.

## Change and review workflow

1. Read the relevant product/API/data-model sections before editing.
2. Make the smallest change that completes the requested slice; avoid unrelated refactors.
3. Preserve existing user data and migrations. If the data model changes, update the schema documentation and migration together.
4. If a change alters product semantics or an ADR, update the source docs and explain the trade-off in the change description.
5. Report what changed and what was verified. Do not claim commands passed unless they were actually run; inspect the repository's current scripts rather than assuming commands exist.
6. Keep documentation links and examples consistent with implementation changes.

Commit complete, reviewable milestones with clear messages and push them to `main` as authorized by the user. Keep each commit focused. A useful commit/PR description states the user-visible behavior, relevant product requirement/ADR, data migration or privacy impact, and verification performed. No mandatory commit-message convention is set yet.

## Product review checklist

- Does the normal chat flow still work without opening the graph or organizing anything?
- Does a kept/annotated passage remain linked to its original conversation and span?
- Can the assistant retrieve it later for a relevant reason and show its source?
- Is each user relation clearly user-originated, and each AI suggestion clearly pending?
- Does any UI imply more certainty about understanding than the evidence supports?
- Can the user ignore a suggestion without penalty or an accumulating task queue?
- Is there an easy route between a graph concept and the conversation that supports it?
