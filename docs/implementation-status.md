# Implementation status and handoff

This file is the durable project handoff for developers and coding agents. Keep it current at coherent milestones so implementation can resume after an interruption, context reset, or change of agent. The Git repository and code are authoritative; this file is a concise navigation aid, not a duplicate changelog.

## Current state

- **Product stage:** Core product roadmap (Phases 0, 1, 2, and 3) implemented and verified.
- **Current milestone:** Phase 3 complete; Phase 4 (hosted sync or desktop packaging) remains deferred per product specification until requested.
- **Completed:**
  - **Foundation & Autonomous Guidance:** product specification, system architecture, relational/epistemic data model, knowledge model, graph projection design, retrieval & AI pipeline, API design, ADRs, and `AGENTS.md`.
  - **Phase 0 — Project scaffold and contracts (`bfc409c`):**
    - Locked Python (`pyproject.toml`, `uv.lock`) and Frontend (`frontend/package.json`, `frontend/package-lock.json`) toolchains.
    - SQLAlchemy 2.0 relational schema (`src/noema/persistence/models.py`) and Alembic migration `0001_initial_schema` (`alembic/versions/0001_initial_schema.py`) with SQLite WAL mode, foreign keys enforced on every connection, and `search_documents_fts` (FTS5).
    - Domain vocabulary, predicate registry, and standalone `#command` parser (`src/noema/domain/vocabulary.py`).
    - API DTO schemas (`src/noema/api/schemas.py`) and synthetic consented evaluation dataset (`src/noema/fixtures/synthetic_dataset.py`).
  - **Phase 1 — Core interactive prototype:**
    - Chat-first conversation and immutable message persistence (`src/noema/conversations/service.py`) with `Idempotency-Key` support, SSE streaming (`GET /api/v1/turns/{turn_id}/stream`), and separate failure/retry paths for chat generation (`POST /api/v1/turns/{turn_id}/retry`) vs background extraction (`POST /api/v1/turns/{turn_id}/retry-extraction`).
    - Immediate explicit annotations (`#aha`, `#confused`, `#question`, `#connection`, `#hypothesis`, `#revisit`, `#important`) via both UI buttons and typed `#commands` with one-click Undo (`DELETE /api/v1/annotations/{id}`) and no confirmation dialog.
    - Durable SQLite-backed worker queue (`src/noema/worker/runner.py`) with leases, bounded exponential backoff, and idempotent job keys (`knowledge_extraction`, `embedding`), running model calls outside database transactions.
    - Strict separation of source records, provisional world claims (`world_claims`), personal concept states (`user_concept_states`), user-established relations (`user_relations`), and pending AI connection suggestions (`knowledge_suggestions`).
    - Suggestion acceptance (`POST /api/v1/suggestions/{id}/accept`) creates a `user_relations` row (`origin='accepted_suggestion'`) and timeline events without upgrading target concept understanding (`Hebbian learning` remains `self_assessment='unknown'`).
    - React + TypeScript + Tailwind + TanStack Query + Cytoscape.js UI (`frontend/src/`) with chat-first workspace, inline concept pills, quiet contextual suggestion cards, bounded graph view with non-color visual/text cues and accessible outline, concept evidence inspector, and timeline view.
  - **Phase 2 — Retrieval and provenance quality:**
    - Hybrid retrieval (`src/noema/retrieval/service.py`) combining SQLite FTS5 lexical ranking, exact cosine vector similarity (`document_embeddings`), and 1-hop user-relation graph expansion via Reciprocal Rank Fusion (RRF) with explicit boosts for user-authored and `#aha`/`#confused` annotated evidence within a token budget.
    - Evaluated against `SYNTHETIC_CONVERSATIONS` and `RETRIEVAL_EVAL_CASES`.
    - Concept merge (`POST /api/v1/concepts/{id}/merge`) redirecting mentions, claims, relations, and suggestions while preserving aliases and recording a `concept_merged` event.
    - Candidate inferred signal review (`POST /api/v1/concepts/{id}/signals/{evidence_id}/review`) and versioned user hypotheses (`POST /api/v1/messages/{id}/hypotheses`, `POST /api/v1/hypotheses/{id}/revise`).
  - **Phase 3 — Temporal and ownership quality:**
    - Historical graph projection (`GET /api/v1/knowledge/graph?as_of=...`) replaying `knowledge_events` deltas and relation/suggestion timestamps up to `as_of`.
    - Full open-format workspace JSON export (`POST /api/v1/export`) and cascading conversation deletion (`DELETE /api/v1/conversations/{id}`) that cleans up FTS5 rows, embeddings, mentions, annotations, and evidence.
    - Provider configuration & privacy controls (`GET/PUT /api/v1/settings/ai`, `POST /api/v1/settings/ai/validate`) with in-UI API key entry saved to `SecretStore` (`~/.config/noema/secrets.json` `0600`, masked hint returned, never stored in SQLite), live LLM calls + two-model configuration (`conversation_model` big chat LLM + `extraction_model` small background organizer LLM), native Google Gemini (`gemini-3-flash-preview`, `gemini-3.5-flash-lite`, `gemma-4-26b-a4b-it`, `gemma-4-31b-it`) + real-time SSE streaming (`POST /api/v1/conversations/{id}/turns/stream`), remote transfer disclosure, and loopback SSRF validation.
    - Full-screen Obsidian-style hierarchical & semantic-zoom knowledge graph (`frontend/src/components/GraphView.tsx`, `src/noema/knowledge/service.py`) as the default UI surface on a pure black & white frosted-glass theme (`FloatingSidebar.tsx`, `FloatingComposer.tsx`):
      - Color-coded topic groups (`category`) clustered around topic hubs (`hierarchy_level` 1–3) with semantic zoom that simplifies to macro topics when zoomed out and reveals sub-topics when zoomed in, without cluttered edge labels.
      - Hover pop-out card over any node displaying its topic group, `#tags`, saved quote snippet, and source conversation.
      - Seamless transition between Graph view and Chat view, live `Related Chats` in the sidebar (`GET /api/v1/conversations/{id}/related`), and inline `#` tag autocomplete popup (`#aha`, `#confused`, `#question`, `#important`, `#hypothesis`, `#connection`, `#revisit`).
    - Measured latency benchmark (`test_phase3_vector_and_graph_scale_benchmark`) confirming exact vector ranking + FTS5 hybrid search and bounded graph projection complete well under 250 ms.
- **In progress:** none.
- **Next action:** Phase 4 (hosted multi-device sync or Tauri desktop packaging) is deferred by design until requested by the user.
- **Blockers:** none recorded.

## Validation commands and results

- `uv run --offline ruff check .` — passed (`All checks passed!`)
- `uv run --offline pytest` — passed (`8 passed in 3.49s`)
- `uv run --offline alembic upgrade head` — passed (`0001_initial_schema`)
- `npm --prefix frontend run lint` — passed (0 errors)
- `npm --prefix frontend run format:check` — passed (`All matched files use Prettier code style!`)
- `npm --prefix frontend run test` — passed (`2 passed`)
- `npm --prefix frontend run build` — passed (`tsc -b && vite build`)

## Milestone log

| Milestone | Status | Commit | Notes |
|---|---|---|---|
| Product and architecture foundation | Complete | `ec2c616` | See documents linked from [`README.md`](README.md). |
| Autonomous agent and resumption guidance | Complete | `679e0c7` | Root `AGENTS.md` is Antigravity-discoverable; `implementation-status.md` is the persistent handoff. |
| Phase 0: project scaffold and contracts | Complete | `bfc409c` | Tooling locked (`uv.lock`, `package-lock.json`); SQLite + FTS5 migration, domain vocabulary, API schemas, and synthetic eval dataset verified. |
| Phase 1: core interactive prototype | Complete | `995f521` | Chat, typed/UI `#aha` annotation with undo, durable background extraction, evidence-linked Cytoscape/outline graph, suggestion accept/reject, and prior-context retrieval. |
| Phase 2: retrieval and provenance quality | Complete | `995f521` | Hybrid FTS5 + exact vector + graph RRF retrieval, source citations, concept merge, candidate signal review, and versioned user hypotheses. |
| Phase 3: temporal and ownership quality | Complete | `995f521` | Historical `as_of` graph replay, full JSON export, derived-index delete cleanup, provider privacy/SSRF validation, and scale benchmark. |
| Phase 4: deployment direction | Deferred | — | Revisit hosted sync or desktop packaging only when the user asks or validated product needs require it. |

## How to update this file

After each milestone, update its status and commit, revise **Current state** and **Next action**, and record unresolved decisions or blockers. Before stopping work, leave enough detail for another developer to identify the next concrete action without reconstructing conversation history. Never store credentials, secrets, or private user content here.
