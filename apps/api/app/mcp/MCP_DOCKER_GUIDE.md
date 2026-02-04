# Running MCP Server with Docker

This guide shows how to run the Daru PDF MCP (Model Context Protocol) server with Docker for the two-frontend strategy (Web App + Claude Host).

## What Was Created

### MCP Server Implementation

```
apps/api/app/mcp/
├── server.py              # Main MCP server (stdio transport)
├── session.py             # Session management (Y Pattern)
├── storage.py             # Storage utilities
└── tools/
    ├── link_session.py    # Link Claude to SaaS user
    ├── upload_form.py     # Form upload
    ├── autofill_form.py   # AI-powered autofill
    ├── render_preview.py  # Preview generation
    ├── update_field.py    # Field editing
    ├── get_fields.py      # Field listing
    ├── validate_document.py  # Validation
    ├── export_pdf.py      # PDF export (gated)
    └── get_entitlements.py   # Feature access
```

### 10 MCP Tools Available

| Tool | Purpose | Requires Auth |
|------|---------|---------------|
| `link_session` | Link Claude session to user account | No |
| `upload_form` | Upload PDF form | Yes |
| `upload_source_docs` | Upload source documents | Yes |
| `autofill_form` | Auto-fill form fields | Yes |
| `render_preview` | Get page preview | Yes |
| `update_field` | Update field value | Yes |
| `get_fields` | List all fields | Yes |
| `validate_document` | Validate completeness | Yes |
| `export_pdf` | Export filled PDF | Yes (+ entitlement) |
| `get_entitlements` | Check feature access | Yes |

---

## Docker Setup

### Option 1: Run with Docker Compose (Recommended)

```bash
# Navigate to docker-compose directory
cd infra/docker-compose

# Start all services including MCP
docker compose -f docker-compose.dev.yml -f docker-compose.mcp.yml up -d

# View MCP logs
docker compose logs -f mcp

# Check MCP health
curl http://localhost:8001/health
```

### Option 2: Run MCP Service Only

```bash
cd infra/docker-compose

# Start dependencies first
docker compose -f docker-compose.dev.yml up -d redis api

# Then start MCP
docker compose -f docker-compose.mcp.yml up mcp
```

### Option 3: Run Locally (Development)

```bash
cd apps/api

# Install dependencies
pip install -e ".[mcp]"

# Set environment variables
export DARU_SUPABASE_URL="your-url"
export DARU_SUPABASE_SECRET_KEY="your-key"
export DARU_OPENAI_API_KEY="your-key"

# Run MCP server
python -m app.mcp.server
```

---

## Docker Compose Configuration

The MCP service configuration (`docker-compose.mcp.yml`):

```yaml
services:
  mcp:
    build:
      context: ../../apps/api
      dockerfile: Dockerfile.dev
    container_name: daru-mcp
    command: python -m app.mcp.server
    ports:
      - "8001:8001"
    environment:
      - MCP_TRANSPORT=streamable-http
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8001
      - DARU_SUPABASE_URL=${DARU_SUPABASE_URL}
      - DARU_SUPABASE_SECRET_KEY=${DARU_SUPABASE_SECRET_KEY}
      - DARU_OPENAI_API_KEY=${DARU_OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379/2
    depends_on:
      - redis
      - api
    networks:
      - daru-network
```

---

## Connecting to Claude

### For Claude Desktop

Add to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "daru-pdf": {
      "command": "docker",
      "args": [
        "compose",
        "-f", "path/to/docker-compose.dev.yml",
        "-f", "path/to/docker-compose.mcp.yml",
        "run", "--rm", "mcp"
      ]
    }
  }
}
```

### For Claude Code

```bash
# Add MCP server to Claude Code
claude mcp add --transport http daru-pdf http://localhost:8001/mcp

# Verify
claude mcp list
```

---

## Environment Variables

Required in `.env` file:

```bash
# Supabase (for auth & storage)
DARU_SUPABASE_URL=https://xxx.supabase.co
DARU_SUPABASE_SECRET_KEY=your-secret-key

# OpenAI (for autofill)
DARU_OPENAI_API_KEY=sk-...
DARU_OPENAI_MODEL=gpt-4o-mini

# MCP Server
DARU_MCP_PORT=8001

# Redis (for session storage)
REDIS_URL=redis://redis:6379/2
```

---

## Testing the MCP Server

### 1. Check Health

```bash
curl http://localhost:8001/health
# Expected: {"status": "healthy"}
```

### 2. Test Tool Discovery

```bash
# Using MCP protocol
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

### 3. Test Session Linking

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "link_session",
      "arguments": {
        "session_token": "test-token-123"
      }
    },
    "id": 2
  }'
```

---

## Architecture (Y Pattern)

```
┌─────────────────┐
│  Claude Host    │  Entry point (conversation UI)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  MCP Server     │  Port 8001 (Docker)
│  (app/mcp/)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI        │  Port 8000
│  (app/main.py)  │  Core services
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│Supabase│ │ Redis  │
│Auth/DB │ │Sessions│
└────────┘ └────────┘
```

**Flow:**
1. Claude calls MCP tool (e.g., `link_session`)
2. MCP server checks Supabase Auth cookie
3. If logged in → auto-link, no redirect
4. If not → return login URL
5. After login → subsequent calls work seamlessly

---

## Troubleshooting

### MCP Server Won't Start

```bash
# Check logs
docker compose logs mcp

# Common issues:
# - Missing env vars → check .env file
# - Port conflict → change DARU_MCP_PORT
# - Dependencies down → check redis and api
```

### Tools Not Appearing in Claude

```bash
# Restart Claude Desktop/Code
# Verify MCP server is running
curl http://localhost:8001/health

# Check MCP registration
claude mcp list  # For Claude Code
```

### Session Linking Fails

```bash
# Check Redis connection
docker compose exec redis redis-cli PING

# Check Supabase credentials
docker compose exec mcp env | grep SUPABASE
```

---

## Next Steps

1. ✅ MCP server is running
2. [ ] Create Supabase tables (`mcp_sessions`, `entitlements`)
3. [ ] Implement entitlement checks
4. [ ] Add Stripe webhook
5. [ ] Create MCP App UI (iframe)
6. [ ] Deploy to production

See `docs/prd/mcp-core-api/` for full implementation spec.
