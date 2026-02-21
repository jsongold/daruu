# Daru PDF - Training Guide

A comprehensive guide to understanding the Daru PDF document processing system.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Domain Models](#3-domain-models)
4. [Pipeline Workflow](#4-pipeline-workflow)
5. [Service Layer](#5-service-layer)
6. [Orchestrator & Decision Engine](#6-orchestrator--decision-engine)
7. [Repository Pattern](#7-repository-pattern)
8. [API Reference](#8-api-reference)
9. [Processing Strategies](#9-processing-strategies)
10. [Cost Tracking](#10-cost-tracking)
11. [Configuration](#11-configuration)
12. [Deployment](#12-deployment)
13. [Troubleshooting](#13-troubleshooting)
14. [Improving Accuracy](#14-improving-accuracy)

---

## 1. Overview

### What is Daru PDF?

Daru PDF is an intelligent document processing system that automatically fills PDF forms by:
- **Extracting data** from source documents (PDF or images)
- **Mapping fields** between source and target documents
- **Filling target PDFs** with extracted or user-provided values
- **Iterative refinement** with human-in-the-loop when needed

### Key Features

| Feature | Description |
|---------|-------------|
| High-Precision Extraction | Native text + OCR with confidence scoring |
| Coordinate-Based Placement | Accurate field positioning |
| Human-in-the-Loop | Asks questions when uncertain |
| Complete Auditability | Evidence and Activity tracking |
| Cost Management | LLM token and OCR usage tracking |
| Observability | OpenTelemetry tracing, Prometheus metrics |

### Two Operating Modes

```
┌─────────────────────────────────────────────────────────────┐
│  TRANSFER MODE                                              │
│  Copy data from source document to target document          │
│                                                             │
│  Source PDF ──extract──> Values ──fill──> Target PDF        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  SCRATCH MODE                                               │
│  Fill target document from scratch (no source)              │
│                                                             │
│  Questions ──answers──> Values ──fill──> Target PDF         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture

### Project Structure

```
daru-pdf/
├── apps/
│   ├── api/                 # FastAPI backend (main service)
│   │   ├── app/
│   │   │   ├── adapters/    # DTOs, data transformers
│   │   │   ├── application/ # Use cases, port interfaces
│   │   │   ├── domain/      # Pure business logic
│   │   │   ├── infrastructure/  # External integrations
│   │   │   ├── models/      # Pydantic domain models
│   │   │   ├── repositories/    # Repository interfaces
│   │   │   ├── routes/      # FastAPI endpoints
│   │   │   └── services/    # Service layer
│   │   └── tests/
│   ├── orchestrator/        # Pipeline orchestration service
│   ├── web/                 # React + TypeScript frontend
│   └── contracts/           # OpenAPI specs, JSON schemas
├── docs/                    # Documentation
└── infra/
    ├── docker-compose/      # Docker deployment
    ├── gcp/                 # Google Cloud configs
    └── aws/                 # AWS configs
```

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      routes/ (FastAPI)                       │
│           HTTP endpoints, request/response handling          │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                     adapters/ (DTOs)                         │
│            Request/Response models, transformers             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               application/ (Use Cases + Ports)               │
│         Business operations, gateway interfaces              │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   services/ (Coordination)                   │
│          DocumentService, JobService, Orchestrator           │
│           IngestService, ExtractService, FillService         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                 repositories/ (Interfaces)                   │
│        DocumentRepository, JobRepository, FileRepository     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│               infrastructure/ (Implementations)              │
│          Memory repositories, LangChain, Supabase, Redis     │
└─────────────────────────────────────────────────────────────┘
```

### Services Overview

| Service | Responsibility |
|---------|----------------|
| **API** | FastAPI backend, handles all HTTP requests |
| **Orchestrator** | Pipeline execution, decision making |
| **Web** | React frontend for user interaction |
| **Celery Worker** | Async task processing |
| **Redis** | Message broker, result backend |

---

## 3. Domain Models

### Core Entities

#### Document

```python
DocumentType: SOURCE | TARGET

Document:
  id: str                    # Unique identifier
  ref: str                   # File path/storage reference
  document_type: DocumentType
  meta: DocumentMeta
  created_at: datetime

DocumentMeta:
  page_count: int
  file_size: int
  mime_type: str            # application/pdf, image/png, etc.
  filename: str
  has_password: bool
```

#### Field

```python
FieldType: TEXT | NUMBER | DATE | CHECKBOX | RADIO | SIGNATURE | IMAGE | UNKNOWN

FieldModel:
  id: str
  name: str
  field_type: FieldType
  value: str | None
  confidence: float         # 0.0 - 1.0
  bbox: BBox               # Bounding box coordinates
  document_id: str
  page: int
  is_required: bool
  is_editable: bool

BBox:
  x: float                  # Left position (0-1 normalized)
  y: float                  # Top position (0-1 normalized)
  width: float
  height: float
  page: int
```

#### Job

```python
JobMode: TRANSFER | SCRATCH

JobStatus:
  CREATED         # Initial state
  RUNNING         # Pipeline executing
  BLOCKED         # Waiting for user input
  AWAITING_INPUT  # Same as blocked
  DONE           # Successfully completed
  FAILED         # Error occurred

JobContext:
  id: str
  mode: JobMode
  status: JobStatus
  source_document: Document | None
  target_document: Document
  fields: list[FieldModel]
  mappings: list[Mapping]
  extractions: list[Extraction]
  evidence: list[Evidence]
  issues: list[Issue]
  activities: list[Activity]
  progress: float           # 0.0 - 1.0
  iteration_count: int
  cost: CostSummary
  created_at: datetime
  updated_at: datetime
```

### Supporting Models

#### Mapping (Source to Target)

```python
Mapping:
  id: str
  source_field_id: str
  target_field_id: str
  confidence: float
  is_confirmed: bool        # User confirmed
```

#### Evidence (Audit Trail)

```python
EvidenceSource: OCR | LLM | USER | NATIVE_TEXT

Evidence:
  id: str
  field_id: str
  source: EvidenceSource
  bbox: BBox
  confidence: float
  text: str
  document_id: str
```

#### Issue (Problems to Resolve)

```python
IssueType:
  LOW_CONFIDENCE
  MISSING_VALUE
  VALIDATION_ERROR
  MAPPING_AMBIGUOUS
  FORMAT_MISMATCH
  LAYOUT_ISSUE

IssueSeverity: INFO | WARNING | HIGH | CRITICAL | ERROR

Issue:
  id: str
  field_id: str | None
  issue_type: IssueType
  message: str
  severity: IssueSeverity
  suggested_action: str
```

#### Activity (Event Log)

```python
ActivityAction:
  JOB_CREATED
  EXTRACTION_STARTED
  EXTRACTION_COMPLETED
  MAPPING_CREATED
  ANSWER_RECEIVED
  EDIT_APPLIED
  RENDERING_COMPLETED
  ISSUE_DETECTED
  ISSUE_RESOLVED

Activity:
  id: str
  timestamp: datetime
  action: ActivityAction
  details: dict
  field_id: str | None
```

---

## 4. Pipeline Workflow

### Stage Sequence

```
┌────────────────────────────────────────────────────────────────────┐
│                         PIPELINE STAGES                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  INGEST ──> STRUCTURE ──> LABELLING ──> MAP ──> EXTRACT            │
│                                                     │               │
│                                                     ▼               │
│                                      ┌──────────────────────────┐  │
│                                      │  ADJUST ──> FILL ──> REVIEW │
│                                      └───────────────┬──────────┘  │
│                                                      │              │
│                          ┌───────────────────────────┘              │
│                          ▼                                          │
│                  [Issues/Low Confidence?]                           │
│                     │           │                                   │
│                    Yes          No                                  │
│                     │           │                                   │
│                     ▼           ▼                                   │
│              Loop Back       DONE                                   │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### Stage Details

| Stage | Input | Output | Purpose |
|-------|-------|--------|---------|
| **Ingest** | Document file | DocumentMeta, Page images | Validate PDF, extract metadata |
| **Structure** | Page images | Field positions | Detect form structure |
| **Labelling** | Fields, Text | Label-to-field mapping | Link labels to positions |
| **Map** | Source fields, Target fields | Mappings | Match source to target fields |
| **Extract** | Source document | Field values | Extract values from source |
| **Adjust** | Fields, Anchors | Adjusted coordinates | Fix field positions |
| **Fill** | Target PDF, Values | Filled PDF | Write values to PDF |
| **Review** | Filled PDF, Fields | Issues, Confidence | Quality validation |

### Extraction Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTRACTION FLOW                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Try Native PDF Text                                      │
│     └─ Success? ──> confidence = 0.95                       │
│                                                              │
│  2. If no native text, try OCR                               │
│     └─ Success? ──> confidence = OCR confidence              │
│                                                              │
│  3. If conflicts or low confidence, use LLM                  │
│     └─ LLM normalizes and resolves                           │
│                                                              │
│  4. Store Evidence for audit trail                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Service Layer

### Service Structure Pattern

Each service follows this pattern:

```
services/{service_name}/
├── __init__.py          # Public exports
├── service.py           # Main service class (coordination)
├── ports.py             # Interface definitions
├── adapters.py          # External integrations
├── domain/              # Pure business logic
│   ├── __init__.py
│   └── rules.py
└── agents/              # LLM-powered components
    ├── __init__.py
    └── agent.py
```

### Key Services

#### DocumentService

```python
class DocumentService:
    """Handles document upload and management."""

    async def upload_document(
        content: bytes,
        filename: str,
        document_type: DocumentType
    ) -> DocumentResponse:
        """Upload, validate, and process a document."""

    def get_document(document_id: str) -> Document | None:
        """Retrieve document by ID."""

    def get_preview_path(document_id: str, page: int) -> Path | None:
        """Get path to page preview image."""
```

#### JobService

```python
class JobService:
    """Manages job lifecycle."""

    def create_job(request: JobCreate) -> JobContext:
        """Create a new processing job."""

    def get_job(job_id: str) -> JobContext | None:
        """Get job state."""

    async def run_job(
        job_id: str,
        run_mode: RunMode,
        max_steps: int
    ) -> JobContext:
        """Execute job pipeline."""

    def submit_answers(job_id: str, answers: list[FieldAnswer]) -> JobContext:
        """Submit user answers for blocked fields."""

    def submit_edits(job_id: str, edits: list[FieldEdit]) -> JobContext:
        """Apply manual edits to fields."""
```

#### ExtractService

```python
class ExtractService:
    """Extracts values from documents."""

    async def extract_fields(
        document_id: str,
        fields: list[FieldModel],
        strategy_config: StrategyConfig
    ) -> ExtractResult:
        """
        Extract values using configured strategy:
        - LOCAL_ONLY: Native text + OCR only
        - LLM_ONLY: LLM extraction only
        - HYBRID: Local first, LLM enhancement
        - LLM_WITH_LOCAL_FALLBACK: LLM first, fallback to local
        """
```

---

## 6. Orchestrator & Decision Engine

### Orchestrator

The Orchestrator coordinates pipeline execution:

```python
class Orchestrator:
    """Pipeline coordinator."""

    async def run(
        job_id: str,
        run_mode: RunMode,
        max_steps: int = 100
    ) -> JobContext:
        """
        Run modes:
        - STEP: Execute single stage
        - UNTIL_BLOCKED: Run until user input needed
        - UNTIL_DONE: Run to completion
        """
```

### Decision Engine

The DecisionEngine determines what to do after each stage:

```python
class DecisionEngine:
    """Decides next action based on job state."""

    def decide(
        job: JobContext,
        stage_result: StageResult,
        config: OrchestratorConfig
    ) -> NextAction:
        """
        Returns one of:
        - CONTINUE: Proceed to next stage
        - ASK: Request user input
        - MANUAL: Requires human intervention
        - RETRY: Re-run current stage
        - DONE: Job complete
        - BLOCKED: Cannot proceed
        """
```

### Termination Conditions

```
┌─────────────────────────────────────────────────────────────┐
│                  TERMINATION CONDITIONS                      │
│                   (Checked in order)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. DONE                                                     │
│     └─ issues.count == 0 AND confidence >= threshold         │
│                                                              │
│  2. BLOCKED (Infinite Loop Prevention)                       │
│     └─ iteration_count >= max_iterations (default: 10)       │
│                                                              │
│  3. MANUAL (Critical Issues)                                 │
│     └─ Any HIGH or CRITICAL severity issues                  │
│                                                              │
│  4. ASK (Stagnation Detection)                               │
│     └─ improvement_rate < min_improvement_rate (0.1)         │
│                                                              │
│  5. CONTINUE (Default)                                       │
│     └─ Proceed to next stage                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Improvement Rate Calculation

```python
# Weighted issue scoring
SEVERITY_WEIGHTS = {
    CRITICAL: 10,
    HIGH: 5,
    WARNING: 2,
    INFO: 1
}

# Calculate improvement
count_improvement = (prev_count - curr_count) / prev_count
score_improvement = (prev_score - curr_score) / prev_score
improvement_rate = (count_improvement + score_improvement) / 2

# If improvement_rate < 0.1, we're stagnating
```

---

## 7. Repository Pattern

### Interface Definitions

```python
# app/repositories/__init__.py

class DocumentRepository(Protocol):
    """Abstract document storage."""

    def create(document_type, meta, ref) -> Document: ...
    def get(document_id: str) -> Document | None: ...
    def list_all() -> list[Document]: ...
    def delete(document_id: str) -> bool: ...

class JobRepository(Protocol):
    """Abstract job storage."""

    def create(mode, target_document, source_document) -> JobContext: ...
    def get(job_id: str) -> JobContext | None: ...
    def update(job_id: str, **updates) -> JobContext | None: ...
    def add_activity(job_id: str, activity) -> JobContext | None: ...
    def add_field(job_id: str, field) -> JobContext | None: ...
    def add_issue(job_id: str, issue) -> JobContext | None: ...

class FileRepository(Protocol):
    """Abstract file storage."""

    def store(file_id: str, content: bytes, filename: str) -> Path: ...
    def get(file_id: str) -> bytes | None: ...
    def store_preview(document_id: str, page: int, content: bytes) -> Path: ...
    def get_preview_path(document_id: str, page: int) -> Path | None: ...
```

### Implementations

```python
# app/infrastructure/repositories/memory_repository.py

class MemoryDocumentRepository:
    """In-memory implementation for development."""

    def __init__(self):
        self._documents: dict[str, Document] = {}

# Singleton access
def get_document_repository() -> DocumentRepository:
    global _document_repository
    if _document_repository is None:
        _document_repository = MemoryDocumentRepository()
    return _document_repository
```

### Why Singletons Matter

```
⚠️  IMPORTANT: In-Memory Storage Limitation

When running with multiple workers (--workers N), each worker
has its own memory space. Documents uploaded to Worker 1 are
NOT visible to Worker 2.

Solution: Run with --workers 1 for in-memory storage, or use
a shared backend (Redis, PostgreSQL) for production.
```

---

## 8. API Reference

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents` | Upload document (multipart) |
| GET | `/api/v1/documents/{id}` | Get document metadata |
| GET | `/api/v1/documents/{id}/pages/{page}/preview` | Get page preview |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs` | Create job |
| GET | `/api/v1/jobs/{id}` | Get job context |
| POST | `/api/v1/jobs/{id}/run` | Run job |
| POST | `/api/v1/jobs/{id}/answers` | Submit answers |
| POST | `/api/v1/jobs/{id}/edits` | Submit edits |
| GET | `/api/v1/jobs/{id}/review` | Get review data |
| GET | `/api/v1/jobs/{id}/activity` | Get activity log |
| GET | `/api/v1/jobs/{id}/evidence` | Get field evidence |
| GET | `/api/v1/jobs/{id}/output.pdf` | Download filled PDF |
| GET | `/api/v1/jobs/{id}/export.json` | Export job data |
| GET | `/api/v1/jobs/{id}/events` | SSE event stream |
| GET | `/api/v1/jobs/{id}/cost` | Get cost breakdown |

### Pipeline Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/ingest` | Ingest document |
| POST | `/api/v1/structure_labelling` | Analyze structure |
| POST | `/api/v1/mapping` | Map fields |
| POST | `/api/v1/extract` | Extract values |
| POST | `/api/v1/adjust` | Adjust coordinates |
| POST | `/api/v1/fill` | Fill PDF |
| POST | `/api/v1/review` | Review job |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness probe |

### Response Format

```python
# Success
{
  "success": true,
  "data": { ... },
  "meta": { ... }
}

# Error
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Job not found: abc123",
    "trace_id": "trace-xyz"  # For 500 errors
  }
}
```

---

## 9. Processing Strategies

### Available Strategies

```python
ProcessingStrategy:
  LOCAL_ONLY              # Fastest, no LLM costs
  LLM_ONLY                # Best understanding, higher cost
  HYBRID                  # Local first, LLM enhancement (default)
  LLM_WITH_LOCAL_FALLBACK # LLM first, fallback to local
```

### Strategy Configuration

```python
StrategyConfig:
  strategy: ProcessingStrategy
  skip_llm_on_high_confidence: bool = True
  high_confidence_threshold: float = 0.9
  llm_timeout_seconds: int = 30
  fallback_on_llm_error: bool = True
  max_llm_retries: int = 2
```

### Usage Example

```python
# Fast local processing
service = ExtractService(
    strategy_config=StrategyConfig(
        strategy=ProcessingStrategy.LOCAL_ONLY
    )
)

# High-quality LLM processing
service = ExtractService(
    strategy_config=StrategyConfig(
        strategy=ProcessingStrategy.HYBRID,
        high_confidence_threshold=0.95
    )
)
```

---

## 10. Cost Tracking

### Cost Model

```python
CostSummary:
  llm_tokens_input: int
  llm_tokens_output: int
  llm_calls: int
  ocr_pages_processed: int
  ocr_regions_processed: int
  storage_bytes_uploaded: int
  storage_bytes_downloaded: int
  estimated_cost_usd: float
  breakdown:
    llm_cost_usd: float
    ocr_cost_usd: float
    storage_cost_usd: float
  model_name: str
```

### Default Pricing

| Service | Unit | Cost |
|---------|------|------|
| GPT-4o Input | 1M tokens | $2.50 |
| GPT-4o Output | 1M tokens | $10.00 |
| GPT-4o-mini Input | 1M tokens | $0.15 |
| GPT-4o-mini Output | 1M tokens | $0.60 |
| OCR | Per page | $0.0025 |

### Budget Enforcement

```python
# Set via environment variables
DARU_COST_MAX_PER_JOB=1.00      # $1.00 max per job
DARU_COST_WARN_THRESHOLD=0.50   # Warn at $0.50

# Raises BudgetExceededError when limit exceeded
```

---

## 11. Configuration

### Environment Variables

```bash
# Core Settings
DARU_DEBUG=false
DARU_API_PREFIX=/api/v1
DARU_UPLOAD_DIR=/app/uploads
DARU_MAX_UPLOAD_SIZE=52428800  # 50MB

# Orchestrator
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.7
DARU_MAX_ITERATIONS=10
DARU_MIN_IMPROVEMENT_RATE=0.1
DARU_MAX_STEPS_PER_RUN=100

# LLM/OpenAI
DARU_OPENAI_API_KEY=<required>
DARU_OPENAI_MODEL=gpt-4o-mini
DARU_OPENAI_TIMEOUT_SECONDS=120
DARU_OPENAI_MAX_CONCURRENT_REQUESTS=5

# OCR
DARU_OCR_CONFIDENCE_THRESHOLD=0.8
DARU_NATIVE_TEXT_CONFIDENCE=0.95

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Supabase (optional)
DARU_SUPABASE_URL=<project-url>
DARU_SUPABASE_SERVICE_KEY=<key>
```

---

## 12. Deployment

### Docker Compose

```bash
# Start all services
cd infra/docker-compose
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f api

# Rebuild after changes
docker compose build api
docker compose up -d api
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI backend |
| web | 5173 | React frontend |
| orchestrator | 8001 | Pipeline orchestrator |
| redis | 6379 | Message broker |
| celery-worker | - | Async task processor |

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Ready check
curl http://localhost:8000/health/ready

# Celery health
docker compose exec celery-worker celery -A app.infrastructure.celery inspect ping
```

---

## 13. Troubleshooting

### Common Issues

#### "Target document not found" when creating job

**Cause:** Multiple uvicorn workers with in-memory storage.

**Solution:**
```yaml
# docker-compose.yml
api:
  command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

#### Job stuck in RUNNING state

**Cause:** Worker crashed or LLM timeout.

**Solutions:**
1. Check Celery worker logs: `docker compose logs celery-worker`
2. Increase timeout: `DARU_OPENAI_TIMEOUT_SECONDS=180`
3. Check Redis connection

#### Low confidence scores

**Solutions:**
1. Check PDF quality
2. Lower `DARU_DEFAULT_CONFIDENCE_THRESHOLD`
3. Use `HYBRID` strategy with LLM enhancement
4. Provide manual answers for problematic fields

#### PDF fill issues (overflow/overlap)

**Solutions:**
1. Check bounding box calculations
2. Verify page rotation in Ingest
3. Try smaller font sizes via `render_params`

### Debug Mode

```bash
# Enable debug logging
DARU_DEBUG=true docker compose up -d api

# View detailed logs
docker compose logs -f api | grep -E "(DEBUG|ERROR)"
```

---

## 14. Improving Accuracy

This section covers strategies to achieve higher accuracy in document processing.

### 14.1 Document Quality

The quality of input documents directly impacts extraction accuracy.

#### PDF Best Practices

| Factor | Recommendation | Impact |
|--------|----------------|--------|
| **Resolution** | 300 DPI minimum | Higher = better OCR |
| **Text Type** | Native/searchable PDF | Native text = 95% confidence |
| **Scan Quality** | Clean, high contrast | Reduces OCR errors |
| **Orientation** | Correct rotation | Prevents coordinate issues |
| **File Size** | < 50MB | Faster processing |

#### Image Best Practices

```
✓ Use PNG or TIFF for forms (lossless)
✓ Minimum 150 DPI, recommended 300 DPI
✓ Ensure text is sharp and readable
✓ Avoid shadows, glare, or skew
✓ Crop to document boundaries
```

### 14.2 Processing Strategy Selection

Choose the right strategy based on your accuracy vs. cost requirements:

```
┌─────────────────────────────────────────────────────────────────┐
│                    STRATEGY SELECTION GUIDE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HIGH ACCURACY NEEDED?                                           │
│       │                                                          │
│       ├─ YES ──> Use HYBRID or LLM_ONLY                         │
│       │          - Set high_confidence_threshold = 0.95          │
│       │          - Enable LLM normalization                      │
│       │                                                          │
│       └─ NO ───> Use LOCAL_ONLY                                  │
│                  - Fastest, lowest cost                          │
│                  - Good for high-quality native PDFs             │
│                                                                  │
│  MIXED DOCUMENT QUALITY?                                         │
│       │                                                          │
│       └─ YES ──> Use LLM_WITH_LOCAL_FALLBACK                    │
│                  - LLM for complex cases                         │
│                  - Local for simple, high-confidence fields      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 14.3 Confidence Threshold Tuning

Adjust thresholds based on your accuracy requirements:

```python
# High Accuracy (Strict) - More user questions, fewer errors
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.85
DARU_OCR_CONFIDENCE_THRESHOLD=0.90
DARU_NATIVE_TEXT_CONFIDENCE=0.98

# Balanced (Default)
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.70
DARU_OCR_CONFIDENCE_THRESHOLD=0.80
DARU_NATIVE_TEXT_CONFIDENCE=0.95

# High Throughput (Lenient) - Fewer questions, review output
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.50
DARU_OCR_CONFIDENCE_THRESHOLD=0.60
DARU_NATIVE_TEXT_CONFIDENCE=0.90
```

#### Confidence Score Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| 0.95+ | Very High | Auto-accept |
| 0.80-0.95 | High | Usually accept |
| 0.70-0.80 | Medium | Review recommended |
| 0.50-0.70 | Low | Ask user or flag |
| < 0.50 | Very Low | Manual entry needed |

### 14.4 LLM Model Selection

Different models offer different accuracy/cost tradeoffs:

```
┌────────────────┬─────────────┬──────────────┬─────────────────┐
│ Model          │ Accuracy    │ Cost         │ Best For        │
├────────────────┼─────────────┼──────────────┼─────────────────┤
│ gpt-4o         │ Highest     │ $$$          │ Complex forms   │
│ gpt-4o-mini    │ High        │ $            │ Standard forms  │
│ gpt-4-turbo    │ Very High   │ $$           │ Detailed work   │
└────────────────┴─────────────┴──────────────┴─────────────────┘
```

```bash
# For highest accuracy
DARU_OPENAI_MODEL=gpt-4o

# For balanced cost/accuracy (default)
DARU_OPENAI_MODEL=gpt-4o-mini
```

### 14.5 Field-Specific Improvements

#### Handling Low-Confidence Fields

```python
# When a field consistently has low confidence:

1. Check Evidence Sources
   GET /api/v1/jobs/{job_id}/evidence?field_id={field_id}

   → If OCR source: Check scan quality, try re-scan
   → If LLM source: Provide more context in prompts
   → If Native: Check PDF text layer integrity

2. Add Field Hints (Future Feature)
   - Expected format: "MM/DD/YYYY"
   - Value constraints: "numeric, 5 digits"
   - Example values: "12345, 67890"

3. Manual Override
   POST /api/v1/jobs/{job_id}/edits
   {
     "edits": [{
       "field_id": "problematic-field",
       "value": "correct value"
     }]
   }
```

#### Improving Mapping Accuracy

When source-to-target mapping is ambiguous:

```
Problem: Fields "Name" and "Full Name" are confused

Solutions:
1. Use more specific field names in target PDF
2. Provide manual mapping confirmation
3. Lower mapping confidence threshold to trigger questions
4. Review mapping results in UI before extraction
```

### 14.6 Iterative Refinement

The system learns from user corrections within a job:

```
┌──────────────────────────────────────────────────────────────┐
│                   REFINEMENT LOOP                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Initial Extraction ──> Low Confidence Detected               │
│           │                                                   │
│           ▼                                                   │
│  System Asks Questions ──> User Provides Answers              │
│           │                                                   │
│           ▼                                                   │
│  Re-extraction with Context ──> Higher Confidence             │
│           │                                                   │
│           ▼                                                   │
│  Review ──> Issues Resolved? ──> Done                         │
│                    │                                          │
│                    NO                                         │
│                    │                                          │
│                    ▼                                          │
│              Loop Back (max 10 iterations)                    │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 14.7 Accuracy Metrics to Monitor

Track these metrics to identify accuracy issues:

```python
# Per-Job Metrics
job.confidence_summary.average_confidence  # Target: > 0.80
job.confidence_summary.low_confidence_count  # Target: 0
job.issues.count  # Target: 0
job.iteration_count  # Target: < 3

# Aggregate Metrics (via /metrics endpoint)
pipeline_stage_duration_seconds  # Monitor for slowdowns
job_completion_total{status="done"}  # Success rate
error_count  # Should be minimal
```

### 14.8 Common Accuracy Issues and Fixes

| Issue | Symptoms | Solution |
|-------|----------|----------|
| **Poor OCR** | Low confidence on scanned docs | Improve scan quality, use 300 DPI |
| **Field Confusion** | Wrong values in fields | Check mapping, add field hints |
| **Date Formats** | Dates parsed incorrectly | Specify format in extraction |
| **Numbers** | Commas/decimals wrong | Set locale, use validation |
| **Checkboxes** | Not detected | Ensure clear marks, good contrast |
| **Signatures** | Missed or misplaced | Manual placement, larger bbox |
| **Multi-line** | Text truncated | Increase bbox height, wrap text |

### 14.9 Quality Assurance Checklist

Before deploying to production:

```
□ Test with representative document samples
□ Verify confidence thresholds match requirements
□ Check all field types extract correctly
□ Validate date/number formats
□ Test edge cases (empty fields, special characters)
□ Review mapping accuracy for similar field names
□ Measure average confidence across test set
□ Set appropriate cost budget limits
□ Enable monitoring and alerting
□ Plan for manual review workflow
```

### 14.10 Recommended Accuracy Settings by Use Case

#### High-Stakes Documents (Legal, Financial)

```bash
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.90
DARU_OCR_CONFIDENCE_THRESHOLD=0.95
DARU_OPENAI_MODEL=gpt-4o
DARU_PROCESSING_STRATEGY=HYBRID
DARU_MAX_ITERATIONS=15
```

#### Standard Business Forms

```bash
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.75
DARU_OCR_CONFIDENCE_THRESHOLD=0.80
DARU_OPENAI_MODEL=gpt-4o-mini
DARU_PROCESSING_STRATEGY=HYBRID
DARU_MAX_ITERATIONS=10
```

#### High-Volume Processing

```bash
DARU_DEFAULT_CONFIDENCE_THRESHOLD=0.60
DARU_OCR_CONFIDENCE_THRESHOLD=0.70
DARU_OPENAI_MODEL=gpt-4o-mini
DARU_PROCESSING_STRATEGY=LOCAL_ONLY
DARU_MAX_ITERATIONS=5
```

---

## Quick Reference

### Quick-start script (entire pipeline)

A Python script runs the full pipeline. Edit the `CONFIG` section at the top of `tools/quick_start_pipeline.py` (paths, mode, run_mode), then run:

```bash
python tools/quick_start_pipeline.py
```

Default config uses scratch mode and the test asset `apps/tests/assets/2025bun_01_input.pdf` as target; output is written to `tools/output.pdf`. Requires the API to be running (e.g. `docker compose up -d` or `uvicorn` from `apps/api`).

### Job Workflow (Transfer Mode) – curl

```bash
# 1. Upload documents
curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@source.pdf" \
  -F "document_type=source"
# Returns: {"data": {"document_id": "doc-123"}}

curl -X POST http://localhost:8000/api/v1/documents \
  -F "file=@target.pdf" \
  -F "document_type=target"
# Returns: {"data": {"document_id": "doc-456"}}

# 2. Create job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "transfer",
    "source_document_id": "doc-123",
    "target_document_id": "doc-456"
  }'
# Returns: {"data": {"job_id": "job-789"}}

# 3. Run job
curl -X POST http://localhost:8000/api/v1/jobs/job-789/run \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_blocked"}'

# 4. Submit answers if blocked
curl -X POST http://localhost:8000/api/v1/jobs/job-789/answers \
  -H "Content-Type: application/json" \
  -d '{
    "answers": [{"field_id": "field-1", "value": "John Doe"}]
  }'

# 5. Continue to completion
curl -X POST http://localhost:8000/api/v1/jobs/job-789/run \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_done"}'

# 6. Download output
curl http://localhost:8000/api/v1/jobs/job-789/output.pdf -o filled.pdf
```

---

## Design Principles

1. **Clean Architecture** - Strict layer separation
2. **Immutability** - All models frozen, updates create new objects
3. **Port-Adapter Pattern** - Services depend on interfaces
4. **Domain-Driven Design** - Business logic in domain layer
5. **Separation of Concerns** - Services coordinate, Agents reason
6. **Testability** - Abstract ports enable mocking
7. **Observability** - Logging, tracing, metrics at all layers

---

*Last updated: 2026-01-28*
