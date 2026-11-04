# Noema

Noema is a local-first, LLM-native personal knowledge environment. Explore ideas through conversation while the application builds a navigable, evidence-backed model of concepts you have encountered, explored, questioned, connected, or demonstrated understanding of.

## Core Principles

- **Chat is the primary experience:** Ordinary conversation works immediately without required graph maintenance or manual categorization.
- **Strict epistemic separation:** Source material, world claims, user concept states, user-established relations, and AI suggestions are stored and surfaced as distinct layers.
- **Provenance and evidence first:** Every extracted concept mention, world claim, candidate signal, or suggestion links back to exact source messages/spans and model/prompt provenance.
- **No synthetic mastery scores:** Exposure, exploration, explicit self-report (`#aha`, `#confused`), and demonstrated evidence remain independent signals.
- **Local ownership:** Backed by a local SQLite database with FTS5 lexical search, exact vector ranking, append-only `knowledge_events` history, and open JSON export/deletion.

## Documentation

See [`docs/README.md`](docs/README.md) for the full specification and architecture index:
- [Product Specification](docs/product-spec.md)
- [System Architecture](docs/architecture.md)
- [Data Model](docs/data-model.md)
- [Knowledge & Understanding Model](docs/knowledge-model.md)
- [Graph & Visualization](docs/graph-and-visualization.md)
- [Retrieval & AI Pipeline](docs/retrieval-and-ai.md)
- [HTTP API Design](docs/api.md)
- [Decisions & Roadmap](docs/decisions-and-roadmap.md)
- [Implementation Status](docs/implementation-status.md)

## Quick Start

### Start Everything with One Command

```bash
uv run noema
```

This applies any pending SQLite migrations to the local database (`./data/noema.db`), starts the FastAPI backend on `http://127.0.0.1:8000`, and launches the React + Vite UI on **`http://127.0.0.1:5173`** (or serves the built UI directly on `http://127.0.0.1:8000` with `uv run noema --api-only`). Press `Ctrl+C` to stop both cleanly.

### Manual Separate Commands (Optional)

```bash
# Backend
# Optional: migrations also run automatically when the backend starts.
uv run alembic upgrade head
uv run uvicorn noema.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend
npm --prefix frontend run dev
```

### Verification

```bash
uv run ruff check .
uv run pytest
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

