# PRD: Agent-Driven Chat UI — Quick Reference

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Quick Reference

### Core Principles (MUST FOLLOW)

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Auto-fill first** | Fill ALL fields without asking. User edits after. |
| 2 | **LLM = All logic** | No static rules. Agent decides everything. |
| 3 | **Templates = Data** | Visual embedding + bboxes + rules. LLM reads as context. |
| 4 | **Trust the user** | Don't block invalid input. User knows their intent. |
| 5 | **Minimal communication** | "Filled 45 fields." Not long explanations. |

### System Components

| Layer | Components |
|-------|------------|
| **Agents (Reasoning)** | DocumentUnderstanding, Validation, Extraction, Mapping, FormFilling |
| **Services (Execution)** | Document, Template, Bbox, Profile, Learning, VisualEmbedding, PDFRenderer |
| **Tools** | `render_preview`, `render_pdf` |
| **Artifacts** | `filled_pdf`, `preview_image`, `conversation_log`, `ask_user_input` |
| **Ports (Swappable)** | Storage, LLM, VectorDB, Cache, Auth, Embedding |

### Tech Stack Summary

| Layer | Technology |
|-------|------------|
| **Backend** | Python, FastAPI, LangGraph, PyMuPDF, Redis |
| **Frontend** | React + Vite, AI SDK (`useChat`), AI Elements, shadcn/ui, react-dropzone |
| **Database** | Supabase (Postgres + pgvector + Auth + Storage) |

### First Slice to Build

1. Backend: FastAPI + Supabase + document upload endpoint  
2. Frontend: Next.js + chat input + file drop  
3. Agent: Minimal LangGraph calling PyMuPDF  
4. E2E: Upload PDF → Get filled PDF back  

### Development Rules

| Rule | Enforcement |
|------|-------------|
| Small commits | One thing per commit |
| Tests with each commit | Unit tests required |
| E2E for critical paths | Upload→Fill→Download, Edit flow, Auth flow |
| Parallel agents | Backend + Frontend + Tests can run in parallel |
| Main agent integrates | Only main agent commits to main branch |
