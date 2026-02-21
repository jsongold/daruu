# PRD: Agent-Driven Chat UI — Coding Architecture Rules

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Coding Architecture Rules

**Goal:** All external services swappable without changing business logic.

### Architectural Patterns (MUST USE)

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Adapter Pattern** | All external services | Swap implementations via interface |
| **Repository Pattern** | Data access | Abstract DB/storage operations |
| **Ports & Adapters** | Core domain | Isolate business logic from infrastructure |
| **Dependency Injection** | All services | Constructor injection, no hardcoded dependencies |

### Swappable Services

| Service | Interface | Implementations |
|---------|-----------|-----------------|
| Storage | `StoragePort` | Supabase, S3, GCS |
| LLM | `LLMPort` | OpenAI, Anthropic, Local |
| Vector DB | `VectorDBPort` | PgVector, Pinecone, Qdrant |
| Cache | `CachePort` | Redis, Memory |
| Auth | `AuthPort` | Supabase, Auth0, Clerk |
| Embedding | `EmbeddingPort` | OpenAI CLIP, Vertex, Local |

### Code Structure

```
app/
├── domain/           # Core logic (NO external deps)
│   ├── models/
│   ├── services/
│   └── ports/        # Interfaces
├── adapters/         # Implementations (storage/, llm/, vector_db/, ...)
├── config.py         # Load adapters from env
└── main.py           # Wire dependencies
```

### Coding Rules

- Port interfaces in `domain/ports/`.
- Adapters implement ports; no business logic in adapters.
- Swap via env (e.g. `STORAGE=supabase` → `S3Adapter`).
- Frontend: same pattern for API client, auth, storage.

See [agent-chat-ui.md](../agent-chat-ui.md) § Coding Architecture Rules for Port/Adapter examples and swapping steps.
