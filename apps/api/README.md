# Daru PDF API

FastAPI-based API for the Daru PDF document processing system.

## Features

- Document upload and management (source/target PDFs)
- Job creation and execution (transfer/scratch modes)
- LLM-powered field detection and label linking
- Real-time progress via Server-Sent Events (SSE)
- Review, activity log, and evidence retrieval
- PDF output with filled values

## Quick Start

### Prerequisites

- Python 3.11+
- Supabase account (required for storage and database)
- OpenAI API key (for LLM features)

### Installation

```bash
cd apps/api
pip install -e ".[dev]"
```

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Required: Supabase (database and storage)
DARU_SUPABASE_URL=https://xxxxx.supabase.co
DARU_SUPABASE_ANON_KEY=eyJhbGc...
DARU_SUPABASE_SERVICE_KEY=eyJhbGc...  # Optional, for admin operations

# Required: OpenAI (for LLM features)
DARU_OPENAI_API_KEY=sk-...

# Optional: Configuration
DARU_DEBUG=true
DARU_OPENAI_MODEL=gpt-4o-mini
```

### Database Setup

Run migrations against Supabase:

```bash
# List available migrations
python -m app.infrastructure.supabase.migrate --list

# Output combined SQL (run in Supabase SQL Editor)
python -m app.infrastructure.supabase.migrate --output combined.sql
```

Migrations are located in `infra/supabase/migrations/`.

### Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

- API Docs: http://localhost:8000/docs
- OpenAPI Schema: http://localhost:8000/openapi.json

### Running Tests

```bash
# Tests automatically use in-memory storage
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

## Architecture

The project follows Clean Architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        routes/ (API Layer)                           │
│                    FastAPI endpoints, request/response               │
├─────────────────────────────────────────────────────────────────────┤
│                    orchestrator/ (INDEPENDENT)                       │
│              Core pipeline flow control and coordination             │
│         Orchestrator, DecisionEngine, PipelineExecutor               │
├─────────────────────────────────────────────────────────────────────┤
│                        agents/ (LLM Layer)                           │
│              LLM-powered agents for intelligent tasks                │
│      FieldLabellingAgent, ValueExtractionAgent, MappingAgent         │
├─────────────────────────────────────────────────────────────────────┤
│                      services/ (Business Logic)                      │
│                Pure business logic, no LLM awareness                 │
│      StructureLabellingService, FillService, ExtractService          │
├─────────────────────────────────────────────────────────────────────┤
│                    repositories/ (Data Access)                       │
│              Protocol interfaces for data persistence                │
│         DocumentRepository, JobRepository, FileRepository            │
├─────────────────────────────────────────────────────────────────────┤
│                   infrastructure/ (External)                         │
│              Implementations for external services                   │
│                  Supabase, LangChain, Redis                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Dependency Flow

```
routes → orchestrator → agents → services → repositories → infrastructure
                     ↘ services ↗
```

**Key Principles:**
- **Orchestrator** - Independent module, coordinates pipeline stages
- **Agents** - LLM-powered, call services for business logic
- **Services** - Pure business logic, no LLM awareness
- **Repositories** - Data persistence abstractions

## Project Structure

```
apps/api/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Application settings
│   │
│   ├── orchestrator/           # INDEPENDENT - Pipeline orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Main Orchestrator class
│   │   ├── decision_engine.py  # Next action decisions
│   │   ├── pipeline_executor.py# Stage execution
│   │   ├── service_client.py   # Service integration
│   │   ├── domain/             # Domain rules
│   │   ├── application/        # Use cases and ports
│   │   └── infrastructure/     # External integrations
│   │
│   ├── agents/                 # LLM Agents (same level as services)
│   │   ├── __init__.py
│   │   ├── ports.py            # Agent Protocol interfaces
│   │   ├── llm_wrapper.py      # LLM call utilities
│   │   ├── structure_labelling/
│   │   │   └── field_labelling_agent.py
│   │   ├── extract/
│   │   │   └── value_extraction_agent.py
│   │   └── mapping/
│   │       └── mapping_agent.py
│   │
│   ├── services/               # Business Logic Services
│   │   ├── __init__.py
│   │   ├── document_service.py
│   │   ├── job_service.py
│   │   ├── structure_labelling/
│   │   │   ├── service.py
│   │   │   ├── ports.py
│   │   │   └── domain/
│   │   ├── fill/
│   │   ├── extract/
│   │   ├── ingest/
│   │   └── ...
│   │
│   ├── repositories/           # Repository Interfaces (Protocols)
│   │   ├── __init__.py
│   │   ├── document_repository.py
│   │   ├── job_repository.py
│   │   ├── file_repository.py
│   │   └── supabase/           # Supabase implementations
│   │       ├── document_repository.py
│   │       ├── job_repository.py
│   │       └── file_repository.py
│   │
│   ├── infrastructure/         # External Service Adapters
│   │   ├── repositories/       # Repository factory
│   │   │   ├── factory.py      # get_document_repository(), etc.
│   │   │   └── memory_repository.py  # For tests only
│   │   └── supabase/           # Supabase integration
│   │       ├── client.py
│   │       ├── config.py
│   │       └── storage.py
│   │
│   ├── routes/                 # API Endpoints
│   │   ├── auth.py
│   │   ├── documents.py
│   │   ├── jobs.py
│   │   ├── health.py
│   │   └── ...
│   │
│   └── models/                 # Pydantic Models
│       ├── common.py
│       ├── document.py
│       ├── field.py
│       ├── job.py
│       └── ...
│
├── tests/
│   ├── conftest.py             # Test configuration (uses memory repos)
│   └── ...
│
└── pyproject.toml
```

## Import Patterns

```python
# Orchestrator (independent module)
from app.orchestrator import Orchestrator, DecisionEngine, PipelineExecutor

# Agents (at app level, same level as services)
from app.agents import FieldLabellingAgent, ValueExtractionAgent
from app.agents.structure_labelling import LangChainFieldLabellingAgent

# Services (business logic)
from app.services.structure_labelling import StructureLabellingService
from app.services.fill import FillService

# Repositories (use factory functions)
from app.infrastructure.repositories import (
    get_document_repository,
    get_job_repository,
    get_file_repository,
)
```

## API Endpoints

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents` | Upload document |
| GET | `/api/v1/documents/{id}` | Get document metadata |
| GET | `/api/v1/documents/{id}/pages/{page}/preview` | Get page preview |
| GET | `/api/v1/documents/{id}/acroform` | Get AcroForm fields |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs` | Create job |
| GET | `/api/v1/jobs/{id}` | Get job context |
| POST | `/api/v1/jobs/{id}/run` | Run job |
| POST | `/api/v1/jobs/{id}/answers` | Submit field answers |
| GET | `/api/v1/jobs/{id}/review` | Get review data |
| GET | `/api/v1/jobs/{id}/activity` | Get activity log |
| GET | `/api/v1/jobs/{id}/output.pdf` | Download filled PDF |
| GET | `/api/v1/jobs/{id}/events` | SSE event stream |

### Pipeline Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Analyze document structure |
| POST | `/api/v1/extract` | Extract values from source |
| POST | `/api/v1/fill` | Fill target document |

## Configuration

All settings use the `DARU_` prefix:

### Required

| Variable | Description |
|----------|-------------|
| `DARU_SUPABASE_URL` | Supabase project URL |
| `DARU_SUPABASE_ANON_KEY` | Supabase anonymous key |
| `DARU_OPENAI_API_KEY` | OpenAI API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DARU_DEBUG` | `false` | Enable debug mode |
| `DARU_API_PREFIX` | `/api/v1` | API route prefix |
| `DARU_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `DARU_SUPABASE_SERVICE_KEY` | - | Service role key (admin) |
| `DARU_STORAGE_BUCKET_DOCUMENTS` | `documents` | PDF storage bucket |
| `DARU_STORAGE_BUCKET_PREVIEWS` | `previews` | Preview images bucket |

### Test Mode

For tests, set `DARU_REPOSITORY_MODE=memory` to use in-memory repositories (automatically set in `conftest.py`).

## Development

### Adding a New Agent

1. Create agent in `app/agents/<domain>/`:
```python
# app/agents/my_domain/my_agent.py
from app.agents.ports import AgentPort

class MyAgent(AgentPort):
    async def process(self, ...):
        # LLM-powered logic
        pass
```

2. Export in `app/agents/__init__.py`

3. Use in orchestrator or services

### Adding a New Service

1. Create service in `app/services/<domain>/`:
```python
# app/services/my_domain/service.py
class MyService:
    def __init__(self, repository: MyRepository):
        self._repo = repository

    async def do_something(self, ...):
        # Pure business logic (no LLM)
        pass
```

2. Define ports/interfaces in `ports.py`
3. Implement adapters if needed

### Testing

Tests automatically use in-memory repositories:

```python
# conftest.py sets DARU_REPOSITORY_MODE=memory
# No Supabase configuration needed for tests

def test_my_feature(client):
    response = client.post("/api/v1/documents", ...)
    assert response.status_code == 200
```

## Workflow Example

```python
import requests

BASE = "http://localhost:8000/api/v1"

# 1. Upload document
with open("form.pdf", "rb") as f:
    r = requests.post(f"{BASE}/documents", files={"file": f}, data={"document_type": "target"})
doc_id = r.json()["data"]["document_id"]

# 2. Create job
r = requests.post(f"{BASE}/jobs", json={"mode": "scratch", "target_document_id": doc_id})
job_id = r.json()["data"]["job_id"]

# 3. Run until blocked
r = requests.post(f"{BASE}/jobs/{job_id}/run", json={"run_mode": "until_blocked"})

# 4. Check status and submit answers if needed
r = requests.get(f"{BASE}/jobs/{job_id}")
if r.json()["data"]["status"] == "blocked":
    # Submit answers
    requests.post(f"{BASE}/jobs/{job_id}/answers", json={
        "answers": [{"field_id": "...", "value": "John Doe"}]
    })
    # Continue
    requests.post(f"{BASE}/jobs/{job_id}/run", json={"run_mode": "until_done"})

# 5. Download output
r = requests.get(f"{BASE}/jobs/{job_id}/output.pdf")
with open("output.pdf", "wb") as f:
    f.write(r.content)
```
