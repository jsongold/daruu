# Agent Chat UI PRD — Split by Concern

This folder contains the **Agent-Driven Chat UI for Form Filling** PRD split into separate documents by concern. The original single-file PRD is [../agent-chat-ui.md](../agent-chat-ui.md).

## Index

| File | Concern |
|------|---------|
| [00-overview.md](00-overview.md) | Overview, problem statement, user goals, user types |
| [01-core-features.md](01-core-features.md) | Chat interface, agent behavior, document preview, editing, conversation history |
| [02-technical-architecture.md](02-technical-architecture.md) | Agent system, pipeline integration, API changes, frontend components |
| [03-data-models.md](03-data-models.md) | Conversation, Message, Agent State, User Profile, Batch Job |
| [04-user-flows.md](04-user-flows.md) | Happy path (2 docs), with edits, single document (form only) |
| [05-validation-scenarios.md](05-validation-scenarios.md) | Common/complex/edge/scope-out scenarios, coverage matrix |
| [06-success-phases-resolved.md](06-success-phases-resolved.md) | Success metrics, implementation phases, resolved questions |
| [07-technical-details.md](07-technical-details.md) | DB schema, Redis, API contracts, SSE, error handling, file upload, rate limiting |
| [08-appendix-architecture.md](08-appendix-architecture.md) | Current vs new architecture (diagram) |
| [09-design-decisions.md](09-design-decisions.md) | Philosophy, golden flow, system architecture, agents vs services, template system, UX/data decisions |
| [10-coding-architecture.md](10-coding-architecture.md) | Ports & adapters, swappable services, code structure |
| [11-tech-stack.md](11-tech-stack.md) | Backend/frontend/infra libraries, AI Elements, dependencies |
| [12-saas-model.md](12-saas-model.md) | Multi-tenancy, billing, subscription tiers, usage tracking |
| [13-development-workflow.md](13-development-workflow.md) | Feature slices, commit rules, testing, parallel agents |
| [14-quick-reference.md](14-quick-reference.md) | Core principles, system components, tech stack, first slice, dev rules |

## Usage

- **By concern:** Open the numbered file for the topic you need (e.g. data models → `03-data-models.md`).
- **Full PRD:** Use [../agent-chat-ui.md](../agent-chat-ui.md) for the complete text, including long SQL/OpenAPI/SSE blocks and full scenario tables.
