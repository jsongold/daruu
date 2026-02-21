# PRD: Agent-Driven Chat UI — Development Workflow

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Development Workflow

### Commit Strategy: Feature Slices

Each commit = one small vertical slice, deployable and testable (e.g. "User can upload a document": API + storage → Validator → Frontend upload → E2E).

### Commit Rules

Small (one thing), deployable (don’t break main), tested (unit tests per commit), documented (clear message).

### Testing Strategy

Unit tests: every commit. Integration tests: service boundaries. E2E: critical paths only.

### Critical Paths for E2E

Happy path (Upload → Validate → Template match → Auto-fill → Download), Edit flow, Auth flow.

### Development with Claude Code

Plan slice → per commit: tests first, minimal implementation, run tests, commit, verify CI → add E2E for critical path → review.

### Parallel Development with Agents

Main agent (planner) → spawn sub-agents (Backend, Frontend, Tests, Infra) → main agent integrates, reviews, merges. Contract-first: OpenAPI + types defined before sub-agents. Max 4–5 parallel agents; independent slices; main agent only merges.

### Agent Responsibilities

Main: plan, coordinate, integrate, review. Sub-agents: Backend (API, services, DB), Frontend (pages, components, hooks), Test (unit, integration, E2E), Infra (Docker, CI/CD).

### Service → Sub-Agent Mapping

Backend: Document Validator, Template, Bbox, Document, Extraction, Profile, Learning, Visual Embedding (each = one sub-agent). Frontend: Chat Panel, Preview Panel, Inline Editor, Field Info, Sidebar, File Upload (each = one sub-agent).

### Commit Message Format

`<type>(<scope>): <description>`. Types: feat, fix, test, refactor, docs, chore.

### Dependencies

See [agent-chat-ui.md](../agent-chat-ui.md) § Development Workflow → Dependencies for full `pyproject.toml` and `package.json` snippets and AI Elements install commands.
