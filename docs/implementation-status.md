# Implementation status and handoff

This file is the durable project handoff for developers and coding agents. Keep it current at coherent milestones so implementation can resume after an interruption, context reset, or change of agent. The Git repository and code are authoritative; this file is a concise navigation aid, not a duplicate changelog.

## Current state

- **Product stage:** Phase 0 complete; Phase 1 (core interactive prototype) starting.
- **Current milestone:** Phase 1 — core interactive prototype.
- **Completed:**
  - Product specification, architecture, data/knowledge model, graph and retrieval designs, API proposal, ADRs/roadmap, contributor guide, and persistent handoff guidance.
  - Phase 0 scaffold and contracts: Python (`pyproject.toml`, `uv.lock`, Ruff, Pytest, SQLAlchemy 2.0, Alembic migration `0001_initial_schema`, SQLite WAL + foreign keys + FTS5), TypeScript/React (`frontend/` with Vite, Tailwind, TanStack Query, Cytoscape.js, Vitest, ESLint), domain vocabulary and `#command` parser (`src/noema/domain/vocabulary.py`), API DTO schemas (`src/noema/api/schemas.py`), and synthetic evaluation dataset (`src/noema/fixtures/synthetic_dataset.py`).
- **In progress:** Phase 1 — implementing AI gateway, retrieval, knowledge extraction/discovery, durable background worker, FastAPI endpoints, and React UI.
- **Next action:** implement Phase 1 domain services, worker loop, `/api/v1` endpoints, and interactive chat/annotation/graph/timeline frontend, then verify all 10 first-milestone acceptance criteria.
- **Blockers:** none recorded.
- **Validation results (Phase 0):**
  - `uv run ruff check .` — passed
  - `uv run pytest` — 3 passed
  - `uv run alembic upgrade head` — passed (`0001_initial_schema`)
  - `npm --prefix frontend run lint` — passed
  - `npm --prefix frontend run test` — 1 passed
  - `npm --prefix frontend run build` — passed
- **Foundation baseline:** the product and architecture documents originate in `ec2c616`; later milestone commits are listed below.

## Milestone log

| Milestone | Status | Commit | Notes |
|---|---|---|---|
| Product and architecture foundation | Complete | `ec2c616` | See documents linked from [`README.md`](README.md). |
| Autonomous agent and resumption guidance | Complete | `679e0c7` | Root `AGENTS.md` is Antigravity-discoverable; `implementation-status.md` is the persistent handoff. |
| Phase 0: project scaffold and contracts | Complete | `pending-commit` | Tooling locked (`uv.lock`, `package-lock.json`); SQLite + FTS5 migration, domain vocabulary, API schemas, and synthetic eval dataset verified. |
| Phase 1: core interactive prototype | In progress | — | Chat, typed/UI annotation, background extraction, evidence-linked graph, suggestion action, and prior-context retrieval. |
| Phase 2: retrieval and provenance quality | Not started | — | Hybrid retrieval, source-grounded context, correction/merge, suggestion quality. |
| Phase 3: temporal and ownership quality | Not started | — | Historical graph, export/delete, robust jobs, privacy, accessibility, and measured performance. |
| Phase 4: deployment direction | Deferred | — | Revisit hosted sync or desktop packaging only when the user asks or validated product needs require it. |

## How to update this file

After each milestone, update its status and commit, revise **Current state** and **Next action**, and record unresolved decisions or blockers. Before stopping work, leave enough detail for another developer to identify the next concrete action without reconstructing conversation history. Never store credentials, secrets, or private user content here.
