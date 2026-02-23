---
name: python-backend-patterns
description: Backend architecture patterns and best practices for Python + FastAPI (Pydantic models, dependency injection, service layer, testing).
---

# Python Backend Patterns (FastAPI)

Patterns and conventions for building scalable, maintainable Python backends using FastAPI.

## API Design

### Route organization

- Group routes by domain (e.g. `routes/documents.py`, `routes/templates.py`)
- Keep route handlers thin; push logic into services.

### Response shape

Prefer consistent JSON responses for APIs that are not purely REST-resource driven.

```python
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
```

## Validation (Pydantic)

- Validate at boundaries (request bodies, query params)
- Keep internal domain objects typed and consistent

```python
from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    document_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
```

## Service Layer Pattern

Keep business logic out of route handlers.

```python
class DocumentService:
    def __init__(self, storage):
        self._storage = storage

    async def fetch_pdf_bytes(self, document_id: str) -> bytes:
        return await self._storage.get(document_id)
```

## Dependency Injection (FastAPI `Depends`)

Use `Depends` for wiring, but keep dependencies small and explicit.

```python
from fastapi import Depends

def get_document_service() -> DocumentService:
    return DocumentService(storage=...)
```

## Error Handling

- Use typed exceptions for expected errors
- Convert to HTTP errors at the boundary (routes/middleware)

## Testing

- Unit tests for pure logic
- Integration tests for routes using `TestClient` or `httpx.AsyncClient`
- Mock external services (LLM, storage, network) at the boundary

```python
from fastapi.testclient import TestClient
from apps.api.app.main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
```

## Common Pitfalls

- Dynamic imports make dead-code detection unreliable
- Overusing global singletons (prefer explicit dependency injection)
- Catch-all exceptions in routes (prefer targeted handling)
