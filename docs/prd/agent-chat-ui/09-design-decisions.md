# PRD: Agent-Driven Chat UI — Design Decisions & Architecture

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## PRD Addendum: Design Decisions & Architecture

### Core Philosophy

| Principle | Description |
|-----------|-------------|
| **Auto-fill first** | Fill everything possible without asking. User edits after. |
| **LLM = All logic** | No static rules. Agent handles all decision-making. |
| **Templates = Data** | Visual embedding + bboxes + rules (not code). |
| **Learn from corrections** | Improvements scoped to form type. |
| **Trust the user** | Don't block invalid input. User knows their intent. |
| **Minimal communication** | Professional, short responses. "Filled 45 fields." |

---

### The Golden Flow

```
┌─────────────────────────────────────────────────────────────┐
│   1. USER UPLOADS          2. AGENT AUTO-FILLS (SILENT)     │
│   ┌──────────┐             ┌──────────────────────┐         │
│   │ form.pdf │ ──────────► │ Fill ALL fields      │         │
│   │ source   │             │ - From source docs   │         │
│   └──────────┘             │ - From user profile  │         │
│                            │ - Smart defaults     │         │
│                            │ - Leave unknown blank│         │
│                            └──────────┬───────────┘         │
│                                       ▼                     │
│   3. SHOW RESULT           4. USER ADJUSTS (IF NEEDED)      │
│   ┌──────────────────┐     • Inline edit, chat, or download │
│   │ "Filled 45       │     ZERO QUESTIONS until user edits  │
│   │  fields" [Preview]│                                     │
└─────────────────────────────────────────────────────────────┘
```

---

### System Architecture

**Backend Services:** Document Validator, Template Service, Bbox Service, Document Service, Extraction Service, Profile Service, Learning Service, Visual Embedding Service.

**Frontend:** Chat Panel, Preview Panel, Inline Editor, Field Info Panel, Font Controls, Conversation Sidebar.

### Document Validator Service

Gatekeeper after upload. Checks: quality (clarity, readability), content (is it a form?), format (PDF/PNG/JPG/TIFF). Pass → processing; Fail → reject with reason.

### Font Control Feature

Auto-shrink text to fit bbox; user can adjust family, size, weight, color on field select. Overflow: normal / auto-shrunk badge / truncated + tooltip.

### Agents vs Services (CRITICAL DISTINCTION)

| Layer | Purpose | Powered By |
|-------|---------|------------|
| **Agents** | Reasoning, decisions | LLM (LangGraph) |
| **Services** | Execution, data | Code |

**Agents:** DocumentUnderstanding, Validation, Extraction, Mapping, FormFilling (orchestrator).  
**Services:** Document, Template, Bbox, Profile, Learning, Visual Embedding, PDF Renderer.  
**Tools:** `render_preview`, `render_pdf`. **Artifacts:** `filled_pdf`, `preview_image`, `conversation_log`, `ask_user_input`.

### Input Model

Primary: text. Secondary: `ask_user_input` (keyboard nav). File upload: drag & drop or paste.

### Template System

Template = embedding + bboxes + rules (JSON). Match: visual embedding → vector search → use template or fresh agent analysis. Learning: corrections stored per form type → next user benefits.

### Agent Behavior Decisions

Low confidence → fill anyway, show badge. Format mismatch → auto-convert. Invalid input → fill, don't block. Session resume → silent. Multiple forms → template options. Optional fields → smart defaults. LLM failure → retry 3x then error.

### UX Decisions

Tone: minimal. Thinking: always show. Field click: inline edit + field info. Validation: inline red + tooltip. Undo: full stack. Success: Save + Download.

### Data & Security Decisions

PII: user chooses. PDF storage: opt-in. Profile: auto-save, easy delete. Concurrency: lock conversation.

### Technical Priority Stack

1. Bbox detection (95%+). 2. Field labeling (templates help). 3. Value filling (LLM).

### Architecture Diagram

*(See [agent-chat-ui.md](../agent-chat-ui.md) § PRD Addendum → Architecture Diagram for full ASCII diagram.)*  
Flow: Document Validator → reject or continue → Services (Embedding, Vector DB, Template, Bbox, Document, Learning) → Agent (LLM, tools, artifacts) → Chat UI.
