# Daru PDF

Intelligent document processing system that automatically fills PDF forms through a **ChatGPT-style conversational interface**. Upload your forms and source documents, and let the AI agent auto-fill everything - then edit via chat or inline.

## Overview

Daru PDF provides two interfaces:

### 1. Agent Chat UI (v2 API) - NEW
A conversational interface where users:
- Upload PDF forms and source documents
- Agent **auto-fills all fields** without asking questions
- User reviews preview and edits via chat or inline
- Download completed PDF

**Philosophy:** "Auto-fill first, ask later" - Fill everything, user edits after.

### 2. Pipeline API (v1 API)
Programmatic access for:
- **Transfer Mode (転記)**: Transfer data from source to target document
- **Scratch Mode (スクラッチ)**: Fill forms from scratch with field-by-field input

**File Format Support:**
- PDF files (with or without AcroForm)
- Image files: PNG, JPEG, TIFF, WebP (automatically processed as single-page documents)

### Key Features

- **High-precision extraction**: Native text extraction + OCR when needed
- **Coordinate-based placement**: Precise field positioning using anchor-based relative positioning
- **Iterative refinement**: Loop-based processing with review and human participation until convergence
- **Complete auditability**: Full traceability of where values came from (Evidence) and all changes made (Activity)
- **AcroForm and non-AcroForm support**: Direct field filling or coordinate-based overlay drawing
- **LLM-assisted analysis**: Label-to-position linking using LangChain/OpenAI
- **Cost tracking**: Track LLM tokens and OCR usage with estimated costs
- **Observability**: OpenTelemetry tracing, Prometheus metrics, structured logging
- **Health checks**: Kubernetes-ready liveness and readiness probes

## Repository Layout

- `apps/api`: FastAPI service for document processing, job management, and PDF generation
- `apps/contracts`: OpenAPI specs, JSON schemas, and examples (contract-driven development)
- `apps/web`: Vite + React + TypeScript web UI (includes Agent Chat UI)
- `apps/orchestrator`: Orchestrator service (if separate)
- `docs/`: Documentation including PRDs, orchestrator guides, and architecture notes

## Agent Chat UI

The conversational interface for document processing. Built with React and TypeScript.

### Components

```
apps/web/src/
├── pages/
│   └── ChatPage.tsx        # Main chat page
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx   # Layout container (sidebar + messages + preview)
│   │   ├── ChatSidebar.tsx     # Conversation list with date grouping
│   │   ├── ChatMessages.tsx    # Message list with auto-scroll
│   │   ├── ChatMessage.tsx     # Individual message bubble
│   │   ├── ChatInput.tsx       # Text input with file drop
│   │   └── AgentThinking.tsx   # Thinking indicator with stage
│   └── preview/
│       └── DocumentPreview.tsx # PDF preview with zoom/pan
├── hooks/
│   └── useConversation.ts     # Conversation state management
└── api/
    └── conversationClient.ts  # API client with SSE support
```

### Agent Stages

The agent progresses through stages during form processing:

| Stage | Description |
|-------|-------------|
| `idle` | Waiting for input |
| `analyzing` | Analyzing uploaded documents |
| `confirming` | Confirming document type |
| `mapping` | Mapping fields between documents |
| `filling` | Auto-filling form fields |
| `reviewing` | Ready for user review |
| `complete` | Processing complete |

### Real-time Updates

The chat uses Server-Sent Events (SSE) for real-time agent updates:

```typescript
// Connect to SSE stream
const eventSource = new EventSource(`/api/v2/conversations/${id}/stream`);

// Event types: message, thinking, stage_change, preview_update, complete, error
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle event based on type
};
```

## Quick Start with Docker Compose

The fastest way to run Daru PDF is with Docker Compose.

### Prerequisites

- Docker and Docker Compose (v2.0+)
- OpenAI API key (get one at https://platform.openai.com/api-keys)

### 1. Setup Environment

```bash
# Copy the example environment file
cp infra/docker-compose/.env.example infra/docker-compose/.env

# Edit .env and set your OpenAI API key (required)
# DARU_OPENAI_API_KEY=sk-your-key-here
```

### 2. Start Services

```bash
# Start all services (API, Web UI, Redis)
cd infra/docker-compose
docker compose -f docker-compose.dev.yml up --build

# Or run in detached mode
docker compose -f docker-compose.dev.yml up -d --build
```

### 3. Verify Services

Once started, the services are available at:

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:5173 | Agent Chat interface |
| API | http://localhost:8000 | FastAPI backend |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Health Check | http://localhost:8000/health | Service health |

**Quick verification:**

```bash
# Check API health
curl http://localhost:8000/health

# Check API docs are accessible
curl -s http://localhost:8000/docs | head -5

# List conversations (should return empty array initially)
curl http://localhost:8000/api/v2/conversations
```

### 4. Using the Agent Chat UI

1. Open http://localhost:5173 in your browser
2. Click "New Conversation" or start typing
3. Upload a PDF form (drag & drop or click to upload)
4. Optionally upload a source document to transfer data from
5. The agent will auto-fill all fields
6. Review and edit using:
   - **Chat**: Type "change [field] to [value]"
   - **Inline**: Click on fields in the preview
   - **Undo/Redo**: Ctrl+Z / Ctrl+Shift+Z (Cmd on Mac)
7. Download the filled PDF

### 5. Stop Services

```bash
cd infra/docker-compose
docker compose -f docker-compose.dev.yml down

# To also remove volumes (clears all data)
docker compose -f docker-compose.dev.yml down -v
```

### Optional: Debug Tools

```bash
# Start with log viewer (Dozzle at http://localhost:9999)
docker compose -f docker-compose.dev.yml --profile tools up

# Start with Redis Commander (at http://localhost:8081)
docker compose -f docker-compose.dev.yml --profile debug up
```

---

## Local Development (Without Docker)

### Prerequisites

- Python 3.11+
- pip or poetry
- Node.js 18+ and npm for web UI

### Setup

Use the `Makefile` in the root directory for easy setup:

```bash
# Setup all dependencies
make setup

# Or setup individually
make setup-api      # FastAPI backend
make setup-contracts # Contracts package
make setup-ui       # Web UI (Vite + React + TypeScript)
```

### Running the Services

**Run API:**
```bash
make run-api
```
Starts the FastAPI server at `http://localhost:8000`
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

**Run Web UI:**
```bash
make run-ui
```
Starts the Vite dev server at `http://localhost:5173`

> **Note**: The web UI is a basic starter template. The API can be used standalone via HTTP requests or any HTTP client.

### Environment Variables

The API uses environment variables with the `DARU_` prefix. Create a `.env` file in the project root:

**Core Settings:**
```bash
DARU_DEBUG=false                    # Enable debug mode
DARU_API_PREFIX=/api/v1            # API route prefix
DARU_UPLOAD_DIR=/tmp/daru-pdf-uploads  # Upload directory
DARU_MAX_UPLOAD_SIZE=52428800      # Max upload size (50MB)
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.7  # Default confidence threshold
DARU_MAX_STEPS_PER_RUN=100         # Max pipeline steps per run
```

**LLM Configuration (LangChain/OpenAI):**
```bash
DARU_OPENAI_API_KEY=your-api-key    # Required for LLM features
DARU_OPENAI_MODEL=gpt-4o-mini       # Model for LangChain operations
DARU_OPENAI_BASE_URL=               # Optional: Custom endpoint (e.g., Azure OpenAI)
DARU_OPENAI_TIMEOUT_SECONDS=120     # Request timeout
DARU_OPENAI_MAX_CONCURRENT_REQUESTS=5  # Concurrent request limit
DARU_LLM_ANALYZE_MODE=              # Set to "mock" for testing without LLM
DARU_LANGCHAIN_TRACING=false        # Enable LangSmith tracing
DARU_LANGCHAIN_PROJECT=daru-pdf     # LangSmith project name
DARU_LANGCHAIN_VERBOSE=false        # Verbose LangChain logging
```

**Supabase Configuration (Optional):**
```bash
DARU_SUPABASE_URL=                  # Supabase project URL
DARU_SUPABASE_SERVICE_KEY=          # Service role key (server-side)
DARU_SUPABASE_ANON_KEY=             # Anonymous/public key
DARU_STORAGE_BUCKET_DOCUMENTS=documents    # Bucket for original PDFs
DARU_STORAGE_BUCKET_PREVIEWS=previews      # Bucket for page previews
DARU_STORAGE_BUCKET_CROPS=crops            # Bucket for OCR crop images
DARU_STORAGE_BUCKET_OUTPUTS=outputs        # Bucket for filled PDFs
```

**SSE Settings:**
```bash
DARU_SSE_KEEPALIVE_INTERVAL=15      # SSE keepalive interval (seconds)
```

**Orchestrator Settings:**
```bash
DARU_MAX_ITERATIONS=10              # Max pipeline iterations (loop prevention)
DARU_MIN_IMPROVEMENT_RATE=0.1       # Stagnation detection threshold
```

**OCR Settings:**
```bash
DARU_OCR_CONFIDENCE_THRESHOLD=0.8   # OCR confidence threshold
DARU_NATIVE_TEXT_CONFIDENCE=0.95    # Native PDF text confidence
```

## Observability

The system includes comprehensive observability features (optional dependencies).

### Installation

```bash
# Install with observability dependencies
cd apps/api && pip install -e ".[observability]"
```

### OpenTelemetry Tracing

Pipeline stages are automatically traced with span context propagation:

```python
# Traces are automatically created for:
# - Orchestrator.run() - full job execution
# - PipelineExecutor.execute_stage() - individual stages
# - Agent invocations
```

### Prometheus Metrics

Available at `/metrics` endpoint:

| Metric | Type | Description |
|--------|------|-------------|
| `agent_invocation_count` | Counter | Agent invocation count by agent type |
| `agent_invocation_latency` | Histogram | Agent invocation latency |
| `pipeline_stage_duration` | Histogram | Pipeline stage duration by stage |
| `pipeline_stage_count` | Counter | Pipeline stage execution count |
| `job_completion_total` | Counter | Job completion count by status |
| `active_jobs` | Gauge | Currently active jobs |
| `error_count` | Counter | Error count by type |

### Structured Logging

Logs include job_id correlation for easy request tracing:

```json
{"event": "stage_completed", "job_id": "job-xxx", "stage": "extract", "duration_ms": 1234}
```

## Cost Tracking

Track LLM and OCR usage with estimated costs.

### Usage

Costs are automatically tracked in JobContext:

```bash
# Get job with cost information
curl http://localhost:8000/api/v1/jobs/{job_id}

# Response includes:
{
  "cost": {
    "llm_tokens_input": 1500,
    "llm_tokens_output": 500,
    "llm_calls": 3,
    "ocr_pages_processed": 2,
    "estimated_cost_usd": 0.025,
    "breakdown": {
      "llm_cost_usd": 0.020,
      "ocr_cost_usd": 0.005
    }
  }
}
```

### Pricing Configuration

Default pricing (configurable):
- GPT-4o: $2.50/1M input, $10.00/1M output
- GPT-4o-mini: $0.15/1M input, $0.60/1M output
- OCR: $0.0025/page (estimate)

## Health Checks

Kubernetes-ready health check endpoints.

### Endpoints

| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `GET /health` | Liveness probe | K8s liveness check |
| `GET /health/ready` | Readiness probe | K8s readiness check |

### Response Format

```json
// GET /health/ready
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-26T12:00:00Z",
  "components": [
    {"name": "database", "status": "healthy", "latency_ms": 0.5},
    {"name": "llm", "status": "degraded", "message": "API key not configured"},
    {"name": "storage", "status": "healthy", "latency_ms": 0.3},
    {"name": "job_queue", "status": "healthy", "latency_ms": 0.1}
  ]
}
```

### Status Values

- `healthy`: All checks passed
- `degraded`: Optional components unavailable (service still functional)
- `unhealthy`: Critical components unavailable

## Architecture

The system follows **Clean Architecture** principles with clear separation of concerns:

### Layers

1. **Domain Layer** (`app/models/`, `app/domain/`): Entities, value objects, and domain rules (pure, no infrastructure dependencies)
2. **Application Layer** (`app/application/`): Use cases and business logic (depends only on domain and ports)
3. **Service Layer** (`app/services/`): Business logic coordination and orchestration
4. **Interface Adapters** (`app/routes/`, `app/adapters/`): DTOs, controllers, repository interfaces (ports)
5. **Infrastructure Layer** (`app/infrastructure/`): FastAPI, database, OCR/LLM SDKs, PDF libraries (adapters)

### Pipeline Services

The system processes documents through a sequential pipeline with iterative refinement:

```
Ingest → Structure/Labelling → Map → Extract → Adjust → Fill → Review
                                                                    ↓
                                                              [Loop back if needed]
```

**Service Responsibilities:**

1. **Ingest**: PDF normalization, validation, metadata extraction, page rendering
2. **Structure/Labelling**: Document structure analysis, label-to-position linking (LLM-assisted)
3. **Map**: Field correspondence between source and target documents
4. **Extract**: Value extraction from PDF native text + OCR when needed
5. **Adjust**: Coordinate correction using anchor-relative positioning
6. **Fill**: PDF generation (AcroForm fields or coordinate-based overlays)
7. **Review**: Quality validation, issue detection, confidence scoring
8. **Orchestrator**: Pipeline control, branching decisions, loop termination

### Orchestrator

The Orchestrator manages job execution through the pipeline:

- **Decision Engine**: Analyzes job state and determines next action (continue, retry, ask, done, blocked)
- **Pipeline Executor**: Executes pipeline stages and applies results
- **Service Client**: Calls external pipeline services via HTTP

**Run Modes:**
- `step`: Execute one pipeline step at a time
- `until_blocked`: Run until user input is needed
- `until_done`: Run until job is complete

**Termination Conditions:**
1. **Done**: `issues == 0` AND `confidence >= threshold`
2. **Blocked**: `iteration_count >= max_iterations`
3. **Manual**: Critical/High severity issues require human intervention
4. **Ask**: Improvement rate below threshold or low confidence

## API Usage

### Basic Workflow

#### 1. Upload Documents

```bash
# Upload target PDF or image (required)
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@target.pdf" \
  -F "document_type=target"

# Upload source PDF or image (optional, for transfer mode)
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@source.pdf" \
  -F "document_type=source"

# Upload image file (PNG, JPEG, TIFF, WebP are supported)
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@document.png" \
  -F "document_type=target"
```

**Supported file formats:**
- PDF: `application/pdf`
- PNG: `image/png`
- JPEG: `image/jpeg`
- TIFF: `image/tiff`
- WebP: `image/webp`

Image files are automatically processed as single-page documents.

#### 2. Create Job

```bash
# Transfer mode (with source document)
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "transfer",
    "source_document_id": "doc-xxx",
    "target_document_id": "doc-yyy"
  }'

# Scratch mode (target only)
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "scratch",
    "target_document_id": "doc-yyy"
  }'
```

#### 3. Run Job

```bash
# Run until blocked (needs user input)
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/run \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_blocked"}'

# Run one step at a time
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/run \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "step"}'

# Run until done
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/run \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_done"}'
```

#### 4. Handle Blocked State

```bash
# Get review to see issues
curl http://localhost:8000/api/v1/jobs/{job_id}/review

# Submit answers for blocked fields
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/answers \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [
      {"field_id": "field-xxx", "value": "John Doe"}
    ]
  }'

# Submit manual edits
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/edits \
  -H "Content-Type: application/json" \
  -d '{
    "edits": [
      {"field_id": "field-xxx", "bbox": {"x": 100, "y": 200, "width": 150, "height": 20}}
    ]
  }'
```

#### 5. Download Output

```bash
# Download filled PDF
curl http://localhost:8000/api/v1/jobs/{job_id}/output.pdf -o output.pdf

# Export as JSON
curl http://localhost:8000/api/v1/jobs/{job_id}/export.json -o export.json
```

### Real-time Events (SSE)

```bash
# Stream events (keeps connection open)
curl -N http://localhost:8000/api/v1/jobs/{job_id}/events
```

### Pipeline Endpoints

Direct access to individual pipeline stages:

```bash
# Analyze document structure
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc-xxx", "options": {"use_llm": true}}'

# Extract values from source
curl -X POST http://localhost:8000/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc-xxx", "field_ids": ["f1", "f2"], "use_ocr": true}'

# Fill target document
curl -X POST http://localhost:8000/api/v1/fill \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc-xxx", "values": [{"field_id": "f1", "value": "John"}], "method": "auto"}'

# Get review data
curl -X POST http://localhost:8000/api/v1/review \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job-xxx", "include_diff_images": true, "include_evidence": true}'
```

## API Endpoints

### Conversations (v2 API - Agent Chat)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v2/conversations` | Create new conversation |
| GET | `/api/v2/conversations` | List user's conversations |
| GET | `/api/v2/conversations/{id}` | Get conversation details |
| DELETE | `/api/v2/conversations/{id}` | Delete conversation |
| POST | `/api/v2/conversations/{id}/messages` | Send message (with optional file attachments) |
| GET | `/api/v2/conversations/{id}/messages` | Get conversation messages |
| GET | `/api/v2/conversations/{id}/stream` | SSE stream for real-time updates |
| POST | `/api/v2/conversations/{id}/messages/{msg_id}/approve` | Approve agent proposal |
| GET | `/api/v2/conversations/{id}/download` | Download filled PDF |
| GET | `/api/v2/conversations/{id}/documents/{doc_id}/pages/{page}/preview` | Get page preview |

### Authentication (MVP Stub)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login (stub) |
| POST | `/api/v1/auth/logout` | Logout (stub) |
| GET | `/api/v1/auth/me` | Get current user (stub) |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents` | Upload document (multipart) - supports PDF and image files |
| GET | `/api/v1/documents/{document_id}` | Get document metadata |
| GET | `/api/v1/documents/{document_id}/pages/{page}/preview` | Get page preview (PNG) |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs` | Create job |
| GET | `/api/v1/jobs/{job_id}` | Get job context |
| POST | `/api/v1/jobs/{job_id}/run` | Run job |
| POST | `/api/v1/jobs/{job_id}/answers` | Submit answers |
| POST | `/api/v1/jobs/{job_id}/edits` | Submit manual edits |
| GET | `/api/v1/jobs/{job_id}/review` | Get review data |
| GET | `/api/v1/jobs/{job_id}/activity` | Get activity log |
| GET | `/api/v1/jobs/{job_id}/evidence` | Get field evidence |
| GET | `/api/v1/jobs/{job_id}/output.pdf` | Download output PDF |
| GET | `/api/v1/jobs/{job_id}/export.json` | Export job data |
| GET | `/api/v1/jobs/{job_id}/events` | SSE event stream |

### Pipeline Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Analyze document structure and detect fields |
| POST | `/api/v1/extract` | Extract values from source document |
| POST | `/api/v1/fill` | Fill target document with values |
| POST | `/api/v1/review` | Get comprehensive review data for a job |
| POST | `/api/v1/ingest` | Ingest and normalize PDF |
| POST | `/api/v1/structure_labelling` | Structure analysis and label-to-position linking |
| POST | `/api/v1/mapping` | Map source fields to target fields |
| POST | `/api/v1/adjust` | Adjust field coordinates |

## Contracts Package

The `apps/contracts` package defines API contracts using OpenAPI and JSON Schema for contract-driven development:

```bash
# Install and test contracts
make setup-contracts
make test-contracts

# Generate Pydantic models from schemas
make generate-models
```

**Contents:**
- `openapi/api.yaml`: OpenAPI 3.1 specification
- `schemas/*.json`: JSON Schema definitions (Document, Field, JobContext, Evidence, Activity, etc.)
- `examples/`: Request/response examples for all endpoints

## Development

### Running Tests

```bash
# Run all tests
make test

# Run API tests only
make test-api

# Run with coverage
cd apps/api && pytest tests/ -v --cov=app --cov-report=html
```

### Code Quality

```bash
# Run all checks (lint, type, test)
make check

# Run API checks only
make check-api

# Run contracts checks
make check-contracts

# Run all checks (API + Contracts)
make check-all
```

### Project Structure

See [apps/api/README.md](apps/api/README.md) for detailed project structure and architecture documentation.

## Error Codes

| Code | Status | Description |
|------|--------|-------------|
| VALIDATION_ERROR | 400 | Invalid input (schema violation) |
| UNAUTHORIZED | 401 | Authentication required |
| FORBIDDEN | 403 | Permission denied |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | State conflict (e.g., job not done) |
| UNPROCESSABLE_ENTITY | 422 | Cannot process (e.g., password PDF) |
| INTERNAL_ERROR | 500 | Internal error (includes trace_id) |

## MVP Limitations

- Authentication is stubbed (accepts any credentials) - Supabase Auth adapter ready
- OCR services are mocked - OCRGateway interface defined
- Page previews are placeholder images
- Storage is in-memory (not persistent) - Supabase Storage adapter ready
- LangChain integration stubbed - LLMGateway interface and agent.py ready
- Redis job store is stubbed - interface defined in infrastructure

## Documentation

- **Architecture**: See `apps/api/README.md` for detailed architecture and project structure
- **Agent Design**: See `docs/build_by_agent/agent_def.md` for Orchestrator/Agent/Service/Tool architecture
- **Error Recovery**: See `docs/build_by_agent/ERROR_RECOVERY.md` for error handling patterns
- **Improvement Plan**: See `docs/build_by_agent/IMPROVEMENT_PLAN.md` for roadmap
- **Orchestrator**: See `docs/ORCHESTRATOR_*.md` for orchestrator behavior and examples
- **PRDs**: See `docs/build_by_agent/` for service specifications
- **System Overview**: See `SYSTEM_PROMPT.md` for comprehensive system description

## License

[Add license information if applicable]
