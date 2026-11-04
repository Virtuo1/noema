# Instructions for coding agents

Before changing code or product behavior, read:

1. [`docs/README.md`](docs/README.md) for assumptions and document index.
2. [`docs/product-spec.md`](docs/product-spec.md) for user experience and scope.
3. [`docs/architecture.md`](docs/architecture.md), [`docs/data-model.md`](docs/data-model.md), and [`docs/knowledge-model.md`](docs/knowledge-model.md) for system boundaries and invariants.
4. [`docs/implementation-guide.md`](docs/implementation-guide.md) for repository workflow and code conventions.

The repository is currently a documentation foundation. Follow the first prototype milestone in [`docs/decisions-and-roadmap.md`](docs/decisions-and-roadmap.md); do not implement the entire long-term vision in one change.

Core product invariant: chat is the primary experience and must remain useful without graph maintenance. Never conflate a world claim, user-established knowledge, and an AI suggestion. Preserve provenance and history, and never infer that a user understands a concept from conversation frequency or an assistant explanation.

## Repository access and GitHub workflow

The user authorizes coding agents to read and modify the repository, including creating, editing, moving, or deleting project files as needed for the assigned work. Agents are expected to carry authorized repository work through to a commit and push; do not ask for separate permission to make routine in-repository changes or push a task branch.

Use the current assigned branch when one is provided. Otherwise create a focused `codex/<short-task-name>` branch, commit the completed work, and push it to `origin`. Keep changes scoped, report the branch and commit, and update the relevant documentation as the implementation evolves. Do not force-push, rewrite shared history, change GitHub repository settings, merge into a protected/default branch, deploy, or use credentials for unrelated actions without explicit authorization. If repository permissions or a required credential prevent a push, finish the local work and report the specific blocker rather than claiming it was pushed.
