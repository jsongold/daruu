# Daru PDF

Template-driven PDF generation with a FastAPI backend and a Vite + React editor.

## Overview

- Generate PDFs from JSON templates
- Analyze existing PDF templates into a draft schema (LLM-assisted)
- Edit placements in a web UI
- Optional persistence via Supabase

## Repository layout

- `apps/api`: FastAPI service for analyze/generate/templates/docs endpoints
- `apps/web`: Vite + React editor UI
- `packages/schema`: Shared template schema
- `docs/steps`: Project walkthroughs

## Quickstart

### Setup and Run
Use the `Makefile` in the root directory for easy setup and execution.

**Setup dependencies:**
```bash
make setup
```

**Run API:**
```bash
make run-api
```
(Starts the FastAPI server at `http://localhost:8000`)

**Run Web UI:**
```bash
make run-ui
```
(Starts the Vite dev server at local URL, usually `http://localhost:5173`)

### Environment variables

The API uses the following environment variables:

**LLM Analysis** (required for `/analyze`):
- `OPENAI_API_KEY`: required for LLM analysis
- `OPENAI_MODEL`: optional, defaults to `gpt-4o-mini`
- `OPENAI_BASE_URL`: optional override for the OpenAI API base URL
- `OPENAI_TIMEOUT_SECONDS`: optional, defaults to `120` seconds
- `OPENAI_MAX_CONCURRENT_REQUESTS`: optional, defaults to `5` (1-20, concurrent LLM requests)
- `LLM_ANALYZE_MODE=mock`: skips OpenAI calls and returns a mock template

**Optional**:
- `DEBUG`: set to `true` for detailed logging with cache statistics
- `LOG_LEVEL`: set logging level (default: `INFO`)
- `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (or `SUPABASE_ANON_KEY` / `SUPABASE_KEY`):
  required for persistence endpoints

## Analyze API Usage

The `/analyze` endpoint supports parsing PDF templates into a draft schema using an LLM.

### Basic Usage (Hybrid Strategy - Default)

This uses high-resolution page images and extracted text blocks for maximum accuracy.

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F "file=@/path/to/your.pdf"
```

### Vision-Only Strategy (Low Res)

This uses lower resolution images processing one page at a time. Useful for reducing cost or if text extraction is problematic.

```bash
curl -X POST "http://127.0.0.1:8000/analyze?strategy=vision_low_res" \
  -F "file=@/path/to/your.pdf"
```

## Performance Optimizations

The API includes significant performance optimizations for LLM-based PDF analysis:

### Async HTTP Client with Connection Pooling
- Global async HTTP clients for LLM and general requests
- Automatic connection reuse (10 LLM, 20 general connections)
- Reduces TCP overhead by ~100ms per request after first

### Concurrent Page Processing
- Up to 5 concurrent LLM requests (configurable via `OPENAI_MAX_CONCURRENT_REQUESTS`)
- Multi-page PDFs process 4-5x faster than sequential
- Example: 10-page PDF: 50-60s → 12-15s

### Intelligent Render Caching
- Request-scoped cache eliminates redundant PDF rendering
- 50-70% reduction in rendering overhead within single request
- Automatic cleanup prevents memory leaks

### Retry Strategy with Exponential Backoff
- Smarter retry logic for transient failures
- Respects rate limits without overwhelming API
- Better error handling for partial failures

### Expected Performance
- Multi-page PDFs: **4-5x faster** processing
- Large forms (100+ fields): **2-5x faster** enrichment
- Connection pooling: **~100ms saved** per request (after first)
- Cache hit rate: **50-70%** in typical pipelines

For detailed optimization information, see [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md).

## Development notes

- The step-by-step docs live in `docs/steps`
- Database migration SQL is in `apps/api/migrations`
- API and web checks: `make check`
- Performance optimization guide: [PERFORMANCE_OPTIMIZATIONS.md](PERFORMANCE_OPTIMIZATIONS.md)
- Troubleshooting: [OPTIMIZATION_TROUBLESHOOTING.md](OPTIMIZATION_TROUBLESHOOTING.md)

