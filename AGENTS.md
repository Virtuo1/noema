# Instructions for coding agents

Before changing code or product behavior, read:

1. [`docs/README.md`](docs/README.md) for assumptions and document index.
2. [`docs/product-spec.md`](docs/product-spec.md) for user experience and scope.
3. [`docs/architecture.md`](docs/architecture.md), [`docs/data-model.md`](docs/data-model.md), and [`docs/knowledge-model.md`](docs/knowledge-model.md) for system boundaries and invariants.
4. [`docs/implementation-guide.md`](docs/implementation-guide.md) for repository workflow and code conventions.

This root `AGENTS.md` is the always-on project instruction entry point for Antigravity and other compatible coding agents. Antigravity documents automatic discovery of root `AGENTS.md` files as persistent workspace rules: [Antigravity Rules](https://antigravity.google/docs/rules/).

The repository began as a documentation foundation. When asked to **implement the application**, work autonomously through the core product roadmap in [`docs/decisions-and-roadmap.md`](docs/decisions-and-roadmap.md). Build and verify the product in small milestones, but do not stop after the first prototype milestone when core roadmap work remains. The long-term speculative features and deployment decisions remain out of scope unless requested.

Core product invariant: chat is the primary experience and must remain useful without graph maintenance. Never conflate a world claim, user-established knowledge, and an AI suggestion. Preserve provenance and history, and never infer that a user understands a concept from conversation frequency or an assistant explanation.

## Repository access and GitHub workflow

The user authorizes coding agents to read and modify the repository, including creating, editing, moving, or deleting project files as needed for the assigned work. Agents are expected to carry authorized repository work through to a commit and push; do not ask for separate permission to make routine in-repository changes, commits, or pushes. For this personal project, push completed milestone commits to `main` unless the user names another branch or repository protections prevent it. Do not force-push or rewrite shared history.

Do not stop for routine implementation choices already covered by the docs; use the documented defaults, make reversible choices, and record material decisions in ADRs. Ask the user only when required information or authorization is genuinely unavailable, such as credentials, destructive action, or a product-boundary decision the docs cannot resolve. Continue independent work while resolving a blocker. Do not change GitHub settings, deploy, or use credentials for unrelated actions. If an HTTPS push fails, check whether the configured SSH key can authenticate and use the SSH remote before treating the push as blocked. If no authorized method works, finish local work, record the exact blocker in `docs/implementation-status.md`, and report it accurately.

## Persistent progress and interruption recovery

`docs/implementation-status.md` is the durable handoff record; do not rely on chat history or agent memory for project state.

1. At the start of an implementation session, read the status file, inspect `git status` and recent commits, then reconcile the written status with the actual repository.
2. Work through the core roadmap in small, complete vertical milestones. Before a long-running or risky change, record the active milestone and current next step.
3. After each coherent milestone, update the status file with completed work, current work, exact next action, open blockers/decisions, and validation commands/results. Update relevant product/architecture/API docs when behavior changes.
4. Commit and push completed milestones to `main`. Record the resulting commit in the status file.
5. If interrupted, resume from the status file and actual Git state. Inspect partial/uncommitted work before editing; preserve it, finish or safely recover it, and continue from the next incomplete acceptance criterion. Never restart completed work just because the session changed.
6. Before declaring a milestone complete, run the relevant checks available in the repository, verify the milestone acceptance criteria, fix failures, and record exact commands/results. Never claim an unrun check passed.
7. Keep the status file concise and factual. Do not put secrets, credentials, or private conversation content in it.
