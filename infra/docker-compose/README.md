# Daru PDF - Docker Compose Infrastructure

This directory contains Docker Compose configuration for running the Daru PDF application stack.

## Architecture

```
                                    +------------------+
                                    |     Client       |
                                    +--------+---------+
                                             |
                                             v
+----------------------------------------------------------------------------------------------+
|                                    Docker Network (daru-network)                             |
|                                                                                              |
|    +-------------------+         +-------------------+         +-------------------+          |
|    |       Web         |         |       API         |         |      Redis       |          |
|    |  (React/Nginx)    |-------->|    (FastAPI)      |-------->|    (Broker)      |          |
|    |    Port: 5173/80  |         |    Port: 8000     |         |   Port: 6379     |          |
|    +-------------------+         +--------+----------+         +--------+---------+          |
|                                           |                             |                    |
|                                           v                             v                    |
|                                  +-------------------+         +-------------------+          |
|                                  |  Celery Worker    |         |   Celery Beat    |          |
|                                  |  (Async Tasks)    |<--------|   (Scheduler)    |          |
|                                  +-------------------+         +-------------------+          |
|                                           ^                                                  |
|                                           |                                                  |
|                                  +-------------------+                                        |
|                                  |   Orchestrator    |                                        |
|                                  |   Port: 8001      |                                        |
|                                  +-------------------+                                        |
|                                                                                              |
+----------------------------------------------------------------------------------------------+
```

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- OpenAI API key (for LLM features)

### Development

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure required variables:**
   ```bash
   # Edit .env and set at minimum:
   DARU_OPENAI_API_KEY=sk-proj-your-key-here
   ```

3. **Start all services:**
   ```bash
   docker compose up
   ```

4. **Access the application:**
   - Web UI: http://localhost:5173
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Orchestrator: http://localhost:8001
   - Orchestrator Docs: http://localhost:8001/docs
   - Health Check: http://localhost:8000/health

### Production

1. **Build production images:**
   ```bash
   docker compose -f docker-compose.yml build
   ```

2. **Start without development overrides:**
   ```bash
   docker compose -f docker-compose.yml up -d
   ```

3. **Access the application:**
   - Web UI: http://localhost (port 80)
   - API: http://localhost:8000

## Services

| Service | Description | Port | Health Check |
|---------|-------------|------|--------------|
| `api` | FastAPI backend | 8000 | `/health` |
| `orchestrator` | Pipeline orchestration | 8001 | `/health` |
| `web` | React frontend (Vite dev / Nginx prod) | 5173 / 80 | `/` |
| `redis` | Message broker & cache | 6379 | `redis-cli ping` |
| `celery-worker` | Async task processor | - | `celery inspect ping` |
| `celery-beat` | Scheduled tasks (optional) | - | - |

## Configuration

### Environment Variables

All configuration is done through environment variables. See `.env.example` for the full list.

**Required:**
- `DARU_OPENAI_API_KEY` - OpenAI API key for LLM processing

**Optional but Recommended:**
- `DARU_SUPABASE_URL` - Supabase URL for persistence
- `DARU_SUPABASE_SERVICE_KEY` - Supabase service key

### Processing Strategies

Configure how documents are processed:

```bash
# Use both local and LLM processing (recommended)
DARU_PROCESSING_STRATEGY=hybrid

# Local processing only (no LLM costs)
DARU_PROCESSING_STRATEGY=local_only

# LLM only (highest quality, higher cost)
DARU_PROCESSING_STRATEGY=llm_only
```

## Commands

### Basic Operations

```bash
# Start all services
docker compose up

# Start in background
docker compose up -d

# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v

# View logs
docker compose logs -f

# View logs for specific service
docker compose logs -f api
```

### Development

```bash
# Rebuild after code changes
docker compose up --build

# Start with Redis Commander (debug UI)
docker compose --profile debug up

# Run tests inside container
docker compose exec api pytest

# Access API shell
docker compose exec api bash

# Access Redis CLI
docker compose exec redis redis-cli
```

### Production

```bash
# Build production images
docker compose -f docker-compose.yml build

# Start production stack
docker compose -f docker-compose.yml up -d

# Scale workers
docker compose -f docker-compose.yml up -d --scale celery-worker=4

# Start with scheduled tasks
docker compose -f docker-compose.yml --profile scheduled up -d
```

### Maintenance

```bash
# Check service health
docker compose ps

# View resource usage
docker compose top

# Prune unused resources
docker system prune -f
```

## Volumes

| Volume | Description | Mount Point |
|--------|-------------|-------------|
| `redis-data` | Redis persistence | `/data` |
| `uploads` | Shared upload directory | `/app/uploads` |

## Networks

All services communicate over the `daru-network` bridge network.

Internal DNS names:
- `api` - FastAPI service
- `orchestrator` - Pipeline orchestration service
- `web` - Frontend service
- `redis` - Redis service

## Profiles

Docker Compose profiles allow optional services:

```bash
# Start with debug tools (Redis Commander, MailHog)
docker compose --profile debug up

# Start with scheduled tasks (Celery Beat)
docker compose --profile scheduled up

# Start with both
docker compose --profile debug --profile scheduled up
```

## Troubleshooting

### API not starting

1. Check logs: `docker compose logs api`
2. Verify environment variables are set
3. Ensure Redis is healthy: `docker compose exec redis redis-cli ping`

### Connection refused to API

1. Check API health: `curl http://localhost:8000/health`
2. Verify network connectivity: `docker compose exec web curl http://api:8000/health`

### Redis connection issues

1. Check Redis status: `docker compose exec redis redis-cli ping`
2. Verify connection URL: `CELERY_BROKER_URL=redis://redis:6379/0`

### Celery tasks not processing

1. Check worker logs: `docker compose logs celery-worker`
2. Verify Redis connectivity
3. Check task registration: `docker compose exec celery-worker celery -A app.infrastructure.celery_worker inspect active`

### Out of memory

1. Increase Docker memory limits
2. Reduce worker concurrency: `CELERY_WORKER_CONCURRENCY=2`
3. Set Redis memory limit (already configured at 256MB)

## Checking Job Progression

### Quick Status Check

```bash
# Check job status via API
curl -s http://localhost:8000/api/v1/jobs/{job_id} | jq '.data.status'

# Get full job context
curl -s http://localhost:8000/api/v1/jobs/{job_id} | jq
```

### API Endpoints for Job Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jobs/{job_id}` | GET | Get full job context (status, documents, fields, etc.) |
| `/api/v1/jobs/{job_id}/activity` | GET | Get chronological activity log |
| `/api/v1/jobs/{job_id}/review` | GET | Get review data with issues and confidence |
| `/api/v1/jobs/{job_id}/events` | GET | Stream real-time events (SSE) |
| `/api/v1/jobs/{job_id}/cost` | GET | Get cost breakdown (tokens, API calls) |
| `/api/v1/jobs/{job_id}/task/{task_id}` | GET | Get async task status |

### Job Status Values

| Status | Description |
|--------|-------------|
| `created` | Job created, not yet started |
| `running` | Job is actively processing |
| `blocked` | Waiting for user input (answers/edits) |
| `done` | Successfully completed |
| `failed` | Processing failed |

### Monitoring with Logs

```bash
# Watch all service logs
docker compose logs -f

# Watch API logs only
docker compose logs -f api

# Watch Celery worker logs (task processing)
docker compose logs -f celery-worker

# Watch with timestamps
docker compose logs -f --timestamps api celery-worker
```

### Real-Time Event Streaming (SSE)

Connect to the SSE endpoint for real-time updates:

```bash
# Stream events for a job (Ctrl+C to stop)
curl -N http://localhost:8000/api/v1/jobs/{job_id}/events
```

Event types:
- `connected` - SSE connection established
- `job_started` - Job execution started
- `step_completed` - Processing step finished
- `status_changed` - Job status changed
- `field_updated` - Field value updated
- `job_completed` - Job finished
- `ping` - Keepalive (every 15s)

### Checking Async Task Progress

For jobs running asynchronously via Celery:

```bash
# 1. Start async job
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/run/async \
  -H "Content-Type: application/json" \
  -d '{"run_mode": "until_done"}'

# Response contains task_id
# {"success": true, "data": {"job_id": "...", "task_id": "abc123", ...}}

# 2. Poll task status
curl -s http://localhost:8000/api/v1/jobs/{job_id}/task/{task_id} | jq

# 3. Cancel task if needed
curl -X DELETE http://localhost:8000/api/v1/jobs/{job_id}/task/{task_id}
```

### Activity Log

View the chronological activity log:

```bash
curl -s http://localhost:8000/api/v1/jobs/{job_id}/activity | jq '.data[] | {timestamp, action, details}'
```

### Monitoring via Web UI

1. Open http://localhost:5173
2. Create or select a job
3. The JobViewer component shows:
   - Current status
   - Document previews
   - Field list with values
   - Extraction evidence
   - Activity timeline

### Redis Queue Inspection

```bash
# Access Redis CLI
docker compose exec redis redis-cli

# List all keys
KEYS *

# Check Celery task queue length
LLEN celery

# View pending tasks
LRANGE celery 0 -1

# Check task result (replace task_id)
GET celery-task-meta-{task_id}
```

### Useful Monitoring Scripts

```bash
# Watch job status continuously (every 2 seconds)
watch -n 2 'curl -s http://localhost:8000/api/v1/jobs/{job_id} | jq ".data.status"'

# Monitor cost during processing
watch -n 5 'curl -s http://localhost:8000/api/v1/jobs/{job_id}/cost | jq ".data | {tokens: .llm_tokens_input + .llm_tokens_output, cost: .formatted_cost}"'

# Check all service health
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
```

## Security Considerations

1. **Never commit `.env` files** - Contains secrets
2. **Use strong API keys** - Especially for production
3. **Restrict Redis access** - Not exposed in production
4. **Review CORS settings** - Configure `DARU_ALLOWED_ORIGINS`
5. **Enable HTTPS** - Use a reverse proxy for TLS in production

## Production Deployment

For production deployment, consider:

1. **Use a reverse proxy** (e.g., Traefik, Caddy) for TLS
2. **External Redis** - Use managed Redis for reliability
3. **External database** - Use Supabase or managed Postgres
4. **Log aggregation** - Forward logs to centralized system
5. **Monitoring** - Use `/metrics` endpoint with Prometheus

## File Structure

```
infra/docker-compose/
├── docker-compose.yml          # Main production config
├── docker-compose.override.yml # Development overrides (auto-loaded)
├── .env.example                # Environment template
├── nginx/
│   └── nginx.conf             # Full-stack reverse proxy config
└── README.md                  # This file
```

## Related Documentation

- [API README](../../apps/api/README.md) - API documentation
- [PRD](../../docs/build_by_agent/) - Product requirements
- [Orchestrator Docs](../../docs/ORCHESTRATOR_BASIC_BEHAVIOR.md) - Pipeline documentation
