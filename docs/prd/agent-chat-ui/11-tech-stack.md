# PRD: Agent-Driven Chat UI — Tech Stack

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Tech Stack (Lib-Heavy, Minimal Custom Code)

### Backend (Python/FastAPI)

| Category | Library |
|----------|---------|
| API | FastAPI |
| Agent | LangGraph |
| LLM | langchain-openai, langchain-anthropic |
| PDF Read/Fill/Preview | PyMuPDF (fitz) |
| Embeddings | Pluggable adapter |
| Vector Search | pgvector + Supabase |
| State | Redis |
| Streaming | sse-starlette |
| DB | supabase-py |
| Validation | Pydantic |

### Frontend (React/Vite or Next.js)

| Category | Library |
|----------|---------|
| Framework | Vite + React or Next.js 14+ |
| Chat Streaming | AI SDK (`ai`, `useChat`) |
| Chat UI | AI Elements (Conversation, Message, PromptInput, Response, Actions, Sources, Reasoning, Tool) |
| UI | shadcn/ui |
| File Upload | react-dropzone |
| Auth | @supabase/auth-helpers-nextjs |
| API | @supabase/supabase-js |
| Styling | Tailwind CSS |

### Infrastructure

Database: Supabase Postgres. Vector: pgvector. Auth: Supabase Auth. Storage: Supabase Storage. Cache: Redis (e.g. Upstash).

### What Libraries Handle vs What We Build Custom

**Libraries:** Chat streaming/state, chat UI, agent state machine, PDF detection/fill/render, drag-drop, auth, SSE.  
**Custom:** Template matching logic, agent tools, learning/correction storage, `ask_user_input` rendering.

### Dependencies (Summary)

Backend: fastapi, uvicorn, langgraph, langchain-*, pymupdf, redis, supabase, pydantic, sse-starlette.  
Frontend: react, ai, ai-elements, @supabase/supabase-js, react-dropzone, tailwindcss.

**Installing AI Elements:**  
`npx ai-elements@latest add conversation message prompt-input response` or `npx ai-elements@latest add all`
