# Improvement Plan

Based on architecture analysis of `agent_def.md` alignment.

## Status Legend
- [ ] Pending
- [x] Completed
- [~] In Progress

---

## 1. Complete Stub Implementations (DEFERRED)

| Component | Current State | Action |
|-----------|---------------|--------|
| Supabase storage | Interface only | Wire up credentials, implement adapters |
| LangChain/OpenAI agents | Stubs | Implement actual LLM calls in agents |
| Redis job store | Stub | Integrate for production job persistence |
| Celery/RQ workers | Architecture ready | Add async task processing |

**Status:** Deferred for later phase

---

## 2. Add Comprehensive Tests

- [~] Integration tests for full pipeline execution
- [~] Agent proposal validation tests
- [~] Decision engine edge cases
- [~] Service-level tests with mocked ports

**Status:** In progress

---

## 3. Add Observability Layer

- [x] OpenTelemetry tracing for pipeline stages
- [x] Prometheus metrics for agent invocation rates, latency
- [x] Structured logging with correlation IDs

**Status:** Completed
- Created `app/infrastructure/observability/` with tracing.py, metrics.py, logging.py
- `/metrics` endpoint for Prometheus scraping
- Integrated into Orchestrator and PipelineExecutor

---

## 4. Add Cost Tracking

- [x] CostTracker dataclass
- [x] Track LLM tokens, calls, OCR pages
- [x] Estimated cost calculation

**Status:** Completed
- Created `app/models/cost.py` with immutable CostTracker
- Created `app/services/agents/llm_wrapper.py` for tracking
- Integrated into all 3 agents (ValueExtraction, FieldLabelling, Mapping)
- Added CostSummaryModel to JobContext

---

## 5. Improve Error Recovery Documentation

- [x] Document OCR failure handling
- [x] Document LLM timeout handling
- [x] Document partial success scenarios

**Status:** Completed
- Created `docs/build_by_agent/ERROR_RECOVERY.md` (754 lines)
- Covers all 5 error scenarios with code references

---

## 6. Add Contract Tests

- [~] JSON Schema contracts between frontend/backend
- [~] OpenAPI spec generation from FastAPI routes
- [~] Pact-style tests for service boundaries

**Status:** In progress

---

## 7. Configuration Management

- [x] Centralize all configuration in config.py
- [x] Remove magic numbers from services
- [x] Add validation for config values

**Status:** Completed
- Created 11 config classes (Orchestrator, LLM, OCR, Ingest, Mapping, etc.)
- Environment variable support with DARU_ prefix
- @lru_cache factory functions for performance

---

## 8. Add Health Checks

- [x] Health check endpoint
- [x] Supabase connection check
- [x] LLM connection check
- [x] OCR service check

**Status:** Completed
- Created `app/routes/health.py` with /health and /health/ready
- Created `app/models/health.py` with response models
- Non-blocking checks with 5s timeout
- 17 tests in test_health.py

---

## Quick Wins

- [ ] Add `__all__` exports to all `__init__.py` files
- [ ] Add type hints where missing
- [ ] Add docstrings to Protocol classes
- [x] Create `docker-compose.yml` for local development (exists at `infra/docker-compose/`)
