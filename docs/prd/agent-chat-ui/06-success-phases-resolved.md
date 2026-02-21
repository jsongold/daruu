# PRD: Agent-Driven Chat UI — Success Metrics, Phases, Resolved Questions

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|-----------------|
| Task completion rate | > 90% | Conversations reaching 'completed' status |
| Average turns | < 5 | Messages per completed conversation |
| Time to complete | < 3 min | From first upload to download |
| User satisfaction | > 4.5/5 | Post-completion rating |
| Error rate | < 5% | Failed extractions or fills |

---

## Implementation Phases

> **Note:** Implementation uses parallel agent development. Each phase has multiple sub-agents working concurrently.

### Phase 0: Setup (First Slice)
**Goal:** Minimal working pipeline - upload → auto-fill → download

| Sub-Agent | Tasks |
|-----------|-------|
| **Backend** | FastAPI skeleton, Supabase connection, document upload endpoint |
| **Frontend** | Next.js skeleton, chat input, file drop zone |
| **Infra** | Docker compose, CI/CD pipeline, env configuration |

**E2E Test:** Upload PDF → Get filled PDF back (even with dummy fill)

### Phase 1: Core Agent
**Goal:** LangGraph agent with basic form filling

| Sub-Agent | Tasks |
|-----------|-------|
| **Backend** | LangGraph agent, PyMuPDF bbox detection, PDF filling |
| **Frontend** | SSE streaming, preview display, thinking indicator |
| **Tests** | Unit tests for agent, integration tests for pipeline |

**E2E Test:** Upload form → Agent auto-fills → Download filled PDF

### Phase 2: Template System
**Goal:** Template matching for faster processing

| Sub-Agent | Tasks |
|-----------|-------|
| **Backend** | Visual embedding service, pgvector search, template storage |
| **Frontend** | Template picker (`ask_user_input`), template preview |
| **Tests** | Template matching accuracy tests |

**E2E Test:** Upload known form → Match template → Fast fill

### Phase 3: Edit & Adjust
**Goal:** User can edit filled form

| Sub-Agent | Tasks |
|-----------|-------|
| **Backend** | Edit API, undo/redo state |
| **Frontend** | Inline editor, field info panel, chat commands |
| **Tests** | Edit flow tests |

**E2E Test:** Upload → Fill → Edit via chat → Edit inline → Download

### Phase 4: SaaS Features
**Goal:** Multi-tenancy, billing, usage tracking

| Sub-Agent | Tasks |
|-----------|-------|
| **Backend** | Org schema, Stripe integration, usage tracking |
| **Frontend** | Settings page, billing UI, usage dashboard |
| **Tests** | Billing flow tests |

**E2E Test:** Sign up → Choose plan → Fill form → Check usage

---

## Resolved Questions

| Question | Decision |
|----------|----------|
| **Authentication** | Supabase Auth from day one |
| **Multi-form** | One form per conversation |
| **Templates** | Yes - visual embedding + bboxes + rules |
| **Collaboration** | Lock conversation (single session) |
| **Mobile** | Same responsive experience |
| **PII Retention** | User chooses their strategy |
| **Offline** | Not supported (requires internet) |
