# PRD: Agent-Driven Chat UI — Technical Details

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.  
> **Full content:** Database schema (SQL), Redis schema, OpenAPI contracts, SSE event types, error handling, file upload flow, and rate limiting are in the original PRD (sections "Technical Details" and "Appendix").

## Technical Details

### Database Schema (Supabase)

Covers: `conversations`, `messages`, `message_attachments`, `agent_states`, triggers.  
See [agent-chat-ui.md](../agent-chat-ui.md) § Technical Details → Database Schema for full SQL.

### Redis Schema (Agent State)

- `agent:state:{conversation_id}` — active state (stage, documents, form_fields, extracted_values, pending_questions), TTL 1h  
- `sse:connections:{conversation_id}` — SSE connection registry, TTL 5m  
- `rate:messages:{user_id}` — rate limit counter, 30 msg/min

### API Contracts

REST API (OpenAPI 3): `POST/GET /api/v2/conversations`, `GET/DELETE /api/v2/conversations/{id}`, `POST/GET /api/v2/conversations/{id}/messages`, `GET /api/v2/conversations/{id}/stream`, `POST /api/v2/conversations/{id}/approve`, `GET /api/v2/conversations/{id}/download`.  
See original PRD for full OpenAPI YAML and schema definitions.

### SSE Event Types

`connected`, `thinking`, `message`, `preview`, `approval`, `stage_change`, `error`, `complete`.  
See original PRD for event payload examples.

### Error Handling

Structured `ErrorResponse` with `code`, `message`, `details`, `retry_after`.  
Codes: `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `TOO_MANY_FILES`, `CONVERSATION_NOT_FOUND`, `CONVERSATION_COMPLETED`, `RATE_LIMITED`, `AGENT_TIMEOUT`, `EXTRACTION_FAILED`, `FILL_FAILED`, `LLM_ERROR`.  
Recovery: retry 3x for retryable errors, then user-facing message.

### File Upload Flow

Browser → POST /messages (multipart) → API stores file in Supabase → returns file_ref → create message with attachment → 202 Accepted → trigger agent → SSE thinking/message.

### Rate Limiting

- Messages: 30/minute per user  
- Uploads: 50/hour per user  
- Conversations: 100/day per user  
Redis key pattern: `rate:{action}:{user_id}` with window TTL.
