# PRD: Autofill Mode Selection — Quick vs Detailed

> **Created**: 2026-02-24
> **Updated**: 2026-02-24 (v3 — plain REST, no SSE)
> **Status**: Draft
> **Depends on**: [ARCHITECTURE_MIGRATION_PLAN.md](./ARCHITECTURE_MIGRATION_PLAN.md) (To-Be pipeline)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Mode Definitions](#3-mode-definitions)
4. [User Flow](#4-user-flow)
5. [Detailed Mode: Adaptive Streaming Q&A](#5-detailed-mode-adaptive-streaming-qa)
6. [Label Enrichment (Both Modes)](#6-label-enrichment-both-modes)
7. [Architecture](#7-architecture)
8. [API Contract](#8-api-contract)
9. [Frontend Changes](#9-frontend-changes)
10. [Data Models](#10-data-models)
11. [Implementation Phases](#11-implementation-phases)
12. [Success Metrics](#12-success-metrics)

---

## 1. Problem Statement

Today the autofill pipeline has a single execution mode: it extracts data from
sources, asks the LLM to match fields, and fills the PDF in one shot. This works
well for simple forms with structured data but fails when:

- **The form has conditional logic** — different sections for different entity types
- **Data sources are ambiguous** — multiple candidate values, unstructured text
- **Generic field IDs** (`Text1`, `Text2`) — the LLM has no idea what a field means
- **The user knows things the system does not** — preferred formats, which address to use

Users need a choice between a **fast best-effort fill** and a **guided interactive
fill** where the system asks clarifying questions adaptively.

---

## 2. Goals & Non-Goals

### Goals

| # | Goal |
|---|------|
| G1 | Users can choose Quick or Detailed mode before running autofill |
| G2 | Quick mode = current behavior, zero regression |
| G3 | Detailed mode: the LLM asks questions **one at a time**, each answer informing the next |
| G4 | Questions appear in a Claude-style bottom-center modal |
| G5 | User can bail out at any point with "Just Fill" — system fills with what it has |
| G6 | Language-agnostic — LLM generates questions in the form's language |
| G7 | Label enrichment (nearby PDF text → fields) improves both modes |

### Non-Goals

- Multi-turn chat UI (this is a focused Q&A modal, not a general chat)
- Auto-detecting which mode to use (user chooses explicitly)
- Implementing the full RuleAnalyzer (separate effort; this PRD defines how rules feed into the flow)

---

## 3. Mode Definitions

### Quick Mode (default)

Current pipeline, unchanged except for label enrichment:

```
FormContextBuilder.build()  →  FillPlanner.plan()  →  FormRenderer.render()
  + label enrichment               ↓                        ↓
  (nearby PDF text)          LLM one-shot match         Write PDF
```

- **User interaction**: none
- **LLM calls**: 1
- **Latency**: ~3-8s

### Detailed Mode

An adaptive multi-turn conversation where the LLM asks questions one at a time:

```
FormContextBuilder.build()
  + label enrichment
         ↓
   LLM Turn 1: analyze form + data → ask question 1 (or fill if confident)
         ↓
   [User answers in modal]
         ↓
   LLM Turn 2: with answer 1 → ask question 2 (or fill if enough info)
         ↓
   [User answers in modal]
         ↓
   ... (repeat until LLM decides it has enough info) ...
         ↓
   LLM Final Turn: fill all fields using accumulated answers
         ↓
   FormRenderer.render()
```

- **User interaction**: 1-5 questions (LLM guided to limit)
- **LLM calls**: N+1 (N questions + 1 fill)
- **Latency**: ~5-15s LLM time + user response time
- **User can bail out**: "Just Fill" button on every question

---

## 4. User Flow

### 4.1 Mode Selection

```
User uploads PDF + data sources
         ↓
UI shows mode selector:
  ┌─────────────────────────────────────────────┐
  │  ⚡ Quick Fill          📋 Detailed Fill     │
  │  Best-effort,           Asks questions       │
  │  no questions           for higher accuracy  │
  └─────────────────────────────────────────────┘
         ↓
User clicks "Run Autofill"
```

### 4.2 Quick Mode Flow (unchanged)

```
"Run Autofill" (mode=quick)
  → Spinner: "Filling fields..."
  → Pipeline runs (1 LLM call)
  → Results appear
  → Done
```

### 4.3 Detailed Mode Flow

```
"Run Autofill" (mode=detailed)
  → Spinner: "Analyzing form..."
  → LLM analyzes form context + data sources
  → Claude-style modal appears at bottom center:

  ┌─────────────────────────────────────────────────────┐
  │  This form has sections for both companies and       │
  │  individuals. Which applies to you?                  │
  │                                                       │
  │  ○ Company (法人)                                    │
  │  ○ Individual (個人)                                 │
  │                                                       │
  │  [ Just Fill ]                        [ Submit ]     │
  └─────────────────────────────────────────────────────┘

  → User selects "Company" and clicks Submit
  → Spinner briefly while LLM processes
  → Next question appears (informed by previous answer):

  ┌─────────────────────────────────────────────────────┐
  │  We found two addresses in your data. Which is       │
  │  the company's registered address?                   │
  │                                                       │
  │  ○ 東京都渋谷区神宮前6丁目23番4号 桑野ビル2階       │
  │  ○ 東京都目黒区五本木3-25-15 ハウス五本木 11        │
  │                                                       │
  │  [ Just Fill ]                        [ Submit ]     │
  └─────────────────────────────────────────────────────┘

  → User answers, LLM may ask 1-3 more questions...
  → LLM decides it has enough info
  → Spinner: "Filling fields..."
  → Results appear (higher accuracy than Quick mode)
  → Done
```

### 4.4 "Just Fill" at Any Point

Every question modal has a "Just Fill" button. When clicked:
- All `ASK_USER` fields convert to `SKIP`
- LLM fills with whatever context it has accumulated so far
- Render proceeds immediately
- No further questions

---

## 5. Detailed Mode: Adaptive Streaming Q&A

### 5.1 Core Mechanism

There is **no separate QuestionGenerator component**. The FillPlanner LLM itself
decides what to ask — just like Claude uses `ask_user_input` as a tool.

Each LLM turn, the model receives:
- Form fields (with label enrichment)
- Data sources
- Rules (if available)
- **Conversation history** (previous questions + user answers)

And outputs one of:
1. **A question** — when it needs more information
2. **A fill plan** — when it has enough information to fill all fields

### 5.2 Adaptive Questions

Because each answer feeds back into the next LLM call, questions are adaptive:

```
Turn 1: LLM sees ambiguous form
  → Asks: "Company or Individual?"

Turn 2: User says "Company". LLM now knows to focus on company fields.
  → Asks: "Which address is the company's registered address?"
  (Would NOT have asked this if user said "Individual")

Turn 3: User picks address. LLM now has entity type + address.
  → Decides it has enough info → returns fill plan
```

### 5.3 Question Model (1:N)

A single question can affect multiple fields. The LLM does not need to
enumerate every field_id — it describes the **impact** in context, and
the fill-turn LLM infers which fields to resolve.

```json
{
  "type": "question",
  "question": "This form has sections for companies and individuals. Which applies?",
  "question_type": "single_choice",
  "options": [
    {"id": "opt1", "label": "Company (法人)"},
    {"id": "opt2", "label": "Individual (個人)"}
  ],
  "context": "This determines which section of the form (fields 3-10 vs 11-18) should be filled."
}
```

### 5.4 Question Types

| Type | UI Control | When Used |
|------|-----------|-----------|
| `single_choice` | Radio buttons | Multiple candidate values, conditional sections |
| `multiple_choice` | Checkboxes | Multiple options may apply |
| `free_text` | Text input | Value missing entirely from data |
| `confirm` | Yes/No | Low-confidence match, wants validation |

### 5.5 Prompt-Level Question Guidance

The system prompt for Detailed mode instructs the LLM:

> "Ask only the most impactful questions — those that resolve ambiguity
> for multiple fields or determine which form sections apply. Aim for
> 3-5 questions maximum. Do not ask about fields where you are confident.
> When you have enough information, return a fill plan."

No hard cap in code — the LLM decides when it has enough info.

---

## 6. Label Enrichment (Both Modes)

### 6.1 Problem

PDF fields are often named `Text1`, `Text2`, `Dropdown1`. The LLM gets no
semantic clue about what a field means.

### 6.2 Solution

Before calling FillPlanner, `FormContextBuilder` enriches each field with
**nearby text extracted from the PDF** using proximity matching:

```
Field: Text1 (x=100, y=200, page=1)
Nearby text blocks within 150px: ["法人名（フリガナ）", "法人名", "Name"]
  → label_candidates: [
      {"text": "法人名（フリガナ）", "confidence": 0.92, "page": 1},
      {"text": "法人名", "confidence": 0.85, "page": 1}
    ]
```

### 6.3 Algorithm

- Call `DocumentService.extract_text_blocks(document_id)` to get all text
  spans with bbox coordinates from the target PDF
- For each field with bbox, compute center-to-center Euclidean distance
  to every text block on the same page
- Keep the top-3 nearest blocks within 150px
- Convert distance to confidence score: `1.0 - distance / max_distance`

This is **language-agnostic** — pure geometry, works for any language.

### 6.4 What the LLM Sees

```json
{
  "field_id": "Text1",
  "label": "Text1",
  "type": "text",
  "nearby_labels": ["法人名（フリガナ）", "法人名"]
}
```

Instead of just:
```json
{"field_id": "Text1", "label": "Text1", "type": "text"}
```

### 6.5 Scope

Label enrichment applies to **both Quick and Detailed modes**. It is pure
upside — gives the LLM better context with no added LLM cost.

---

## 7. Architecture

### 7.1 Quick Mode Pipeline

```
┌─────────────┐   ┌──────────┐   ┌──────────────┐
│ FormContext  │──►│FillPlan  │──►│ FormRenderer │
│ Builder     │   │ner       │   │              │
│ +labels     │   │(1 call)  │   │              │
└─────────────┘   └──────────┘   └──────────────┘
```

### 7.2 Detailed Mode Pipeline

```
┌─────────────┐   ┌─────────────────────────────────────┐   ┌──────────────┐
│ FormContext  │──►│ FillPlanner (multi-turn)             │──►│ FormRenderer │
│ Builder     │   │                                       │   │              │
│ +labels     │   │ Turn 1: SSE → question               │   └──────────────┘
└─────────────┘   │ Turn 2: POST answer → SSE → question │
                   │ ...                                   │
                   │ Turn N: POST answer → SSE → fill plan│
                   └─────────────────────────────────────┘
```

### 7.3 Transport: Plain REST Per Turn

Each LLM turn is a **normal POST → JSON response**:

1. Frontend sends POST with form context + conversation history
2. Server calls LLM, waits for response (a short JSON — question or fill plan)
3. Returns JSON response
4. If response is a question: user answers, frontend sends new POST with updated history
5. If response is a fill plan: proceed to render

No SSE, no WebSockets, no long-lived connections. No server-side session state.
Frontend holds all state. The LLM response is a single JSON object (not streamed
tokens), so plain REST is sufficient.

### 7.4 Server Statelessness

The server stores **nothing** between turns. Each SSE request includes:
- Original form context (fields, data sources, rules)
- Full conversation history (all previous questions + answers)

The frontend is the state holder. This keeps the server simple and horizontally
scalable.

### 7.5 Modified Components

| Component | Change |
|-----------|--------|
| **FormContextBuilder** | Add `document_service` dependency, `_enrich_fields_with_labels()` method |
| **FillPlanner** | Accept `mode` parameter. In Detailed mode, LLM can return a question OR a fill plan. Add `plan_turn()` method for single-turn adaptive planning. |
| **FieldFillAction** | Add optional `question` field (for ASK_USER actions) |
| **AutofillPipelineService** | Accept `mode`. Quick = current. Detailed = multi-turn orchestration. |
| **Autofill route** | New SSE endpoint for Detailed mode turns. |
| **Prompts** | Add Detailed mode system prompt variant with `nearby_labels` guidance + ASK_USER instructions. Enrich Quick mode prompt with `nearby_labels` guidance. |

### 7.6 New Components

| Component | Purpose |
|-----------|---------|
| **Turn endpoint** | `POST /api/v1/autofill/turn` — single LLM turn, returns question or fill plan |

---

## 8. API Contract

### 8.1 Quick Mode (unchanged except label enrichment)

```
POST /api/v1/autofill
```

```json
{
  "document_id": "doc_123",
  "conversation_id": "conv_456",
  "fields": [...],
  "rules": [],
  "mode": "quick"
}
```

Response: same as today (filled_fields, unfilled_fields, step_logs).

### 8.2 Detailed Mode — Turn Endpoint

```
POST /api/v1/autofill/turn
```

**Request:**

```json
{
  "document_id": "doc_123",
  "conversation_id": "conv_456",
  "fields": [...],
  "rules": [],
  "conversation": [
    {
      "role": "assistant",
      "type": "question",
      "question": "Company or Individual?",
      "question_type": "single_choice",
      "options": [{"id": "opt1", "label": "Company"}, {"id": "opt2", "label": "Individual"}]
    },
    {
      "role": "user",
      "type": "answer",
      "selected_option_ids": ["opt1"]
    }
  ],
  "just_fill": false
}
```

First request: `conversation` is `[]` (no history yet).
Subsequent requests: `conversation` contains all previous Q&A pairs.

### 8.3 Turn Response — Question

When the LLM needs more information:

```json
{
  "type": "question",
  "question": "Which address is the company's registered address?",
  "question_type": "single_choice",
  "options": [
    {"id": "opt1", "label": "東京都渋谷区神宮前6丁目23番4号 桑野ビル2階"},
    {"id": "opt2", "label": "東京都目黒区五本木3-25-15 ハウス五本木 11"}
  ],
  "context": "This will be used for the filing address fields.",
  "step_logs": [...]
}
```

### 8.4 Turn Response — Fill Plan (final turn)

When the LLM has enough information:

```json
{
  "type": "fill_plan",
  "filled_fields": [...],
  "unfilled_fields": [...],
  "skipped_fields": [...],
  "filled_document_ref": "...",
  "processing_time_ms": 1234,
  "step_logs": [...]
}
```

The server runs FormRenderer before responding, so the fill plan response
includes the rendered document reference.

### 8.5 "Just Fill" (bail out)

Frontend sends a turn with `just_fill: true`:

```json
{
  "document_id": "doc_123",
  "conversation_id": "conv_456",
  "fields": [...],
  "conversation": [...previous Q&A...],
  "just_fill": true
}
```

Server skips further questions and returns a fill plan using accumulated context.
Response shape is identical to 8.4.

---

## 9. Frontend Changes

### 9.1 Mode Selector

Toggle above "Run Autofill" button:

```
  Mode: [ ⚡ Quick | 📋 Detailed ]
```

### 9.2 Question Modal (Claude-style)

Bottom-center floating modal, appears one question at a time:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│  This form has sections for both companies and             │
│  individuals. Which applies to you?                        │
│                                                            │
│  ○ Company (法人)                                          │
│  ○ Individual (個人)                                       │
│                                                            │
│  ───────────────────────────────────────────────           │
│  This determines which section of the form should          │
│  be filled.                                                │
│                                                            │
│  [ Just Fill ]                              [ Submit ]     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Layout:**
- Question text (large)
- Answer controls (radio/checkbox/text input depending on type)
- Context text (small, muted — explains why the system is asking)
- Two buttons: "Just Fill" (secondary) and "Submit" (primary)

**Behavior:**
- Modal appears when turn response has `type: "question"`
- Spinner shown between turns (after Submit, before next response)
- Modal disappears when turn response has `type: "fill_plan"`
- "Just Fill" sends the request with `just_fill: true`

### 9.3 State Management

```typescript
const [autofillMode, setAutofillMode] = useState<'quick' | 'detailed'>('quick')

// Detailed mode conversation state
const [conversation, setConversation] = useState<ConversationTurn[]>([])
const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
const [isStreaming, setIsStreaming] = useState(false)
```

### 9.4 Pipeline Tab

Shows step logs including each turn:
- `context_build` → `turn_1_question` → `turn_1_answer` → `turn_2_question` → ... → `fill_plan` → `render`

---

## 10. Data Models

### 10.1 Conversation Turn (shared frontend/backend)

```python
class ConversationTurn(BaseModel):
    role: str            # "assistant" | "user"
    type: str            # "question" | "answer" | "fill_plan"

    # When role=assistant, type=question:
    question: str | None = None
    question_type: str | None = None   # single_choice | multiple_choice | free_text | confirm
    options: tuple[QuestionOption, ...] = ()
    placeholder: str | None = None
    context: str | None = None

    # When role=user, type=answer:
    selected_option_ids: tuple[str, ...] = ()
    free_text: str | None = None

    model_config = {"frozen": True}
```

### 10.2 Extended FieldFillAction

```python
class FieldFillAction(BaseModel):
    field_id: str
    action: FillActionType           # FILL | SKIP | ASK_USER
    value: str | None = None
    confidence: float = 0.0
    source: str | None = None
    reason: str | None = None
    question: FieldQuestion | None = None  # NEW: for ASK_USER actions
    model_config = {"frozen": True}

class FieldQuestion(BaseModel):
    text: str
    type: QuestionType   # single_choice | multiple_choice | free_text | confirm
    options: tuple[QuestionOption, ...] = ()
    placeholder: str | None = None
    context: str | None = None
    model_config = {"frozen": True}

class QuestionOption(BaseModel):
    id: str
    label: str
    model_config = {"frozen": True}
```

### 10.3 Stream Request

```python
class AutofillStreamRequestDTO(BaseModel):
    document_id: str
    conversation_id: str
    fields: list[AutofillFieldDTO]
    rules: list[str] | None = None
    conversation: list[ConversationTurn] = []
    just_fill: bool = False
    model_config = {"frozen": True}
```

---

## 11. Implementation Phases

### Phase 1: Label Enrichment (both modes)

- Add `document_service` dependency to `FormContextBuilder`
- Implement `_enrich_fields_with_labels()` using proximity matching
- Include `nearby_labels` in FillPlanner fields JSON
- Update prompts to reference `nearby_labels`
- Wire `DocumentService` into `FormContextBuilder` in route handler
- **Both Quick and Detailed modes benefit immediately**

### Phase 2: Mode Plumbing + Quick Mode Prompt Update

- Add `AutofillMode` enum (`quick` | `detailed`)
- Add `mode` field to `AutofillRequestDTO` (default `"quick"`)
- Pass `mode` through pipeline
- Quick mode: current path, now with label enrichment
- Detailed mode: same as Quick for now (no questions yet)
- Frontend: add mode toggle (Quick selected by default)

### Phase 3: Detailed Mode — SSE Endpoint + Single-Turn Question

- Implement `POST /api/v1/autofill/stream` SSE endpoint
- Add Detailed mode system prompt (allows `ask_user` response type)
- FillPlanner: add `plan_turn()` method that returns question OR fill plan
- Frontend: `QuestionModal.tsx` component (Claude-style)
- Single-turn only for now (LLM asks 1 question, then fills)

### Phase 4: Multi-Turn Adaptive Flow

- Frontend: conversation state management, loop of SSE → question → answer
- Backend: `plan_turn()` accepts conversation history
- "Just Fill" button sends `just_fill: true`
- Pipeline tab: show per-turn step logs
- Prompt tuning: guide LLM to ask 3-5 questions max, prioritize high-impact

### Phase 5: Rule Analyzer (separate PRD)

- Replace `RuleAnalyzerStub` with real implementation
- Feed rules into FillPlanner context
- Smarter questions in Detailed mode

---

## 12. Success Metrics

| Metric | Quick Mode Baseline | Detailed Mode Target |
|--------|-------------------|---------------------|
| **Fill accuracy** | Current level | +20-30% improvement |
| **Time to complete** | ~5s | ~10-30s (including user time) |
| **Questions per session** | 0 | 3-5 average |
| **Question relevance** | N/A | >80% rated useful |
| **"Just Fill" bail-out rate** | N/A | <20% |
| **User preference** | N/A | >60% choose Detailed for complex forms |

---

## Appendix A: Prompt Diff

### Quick Mode System Prompt Addition (label enrichment)

```
Each field includes `nearby_labels` — text found near the field on the PDF.
When field_id is generic (Text1, Text2, ...), use nearby_labels to understand
the field's semantic purpose.
```

### Detailed Mode System Prompt

```
You are a form-filling assistant. You can either:
1. Ask the user a clarifying question (when data is ambiguous or missing)
2. Return a fill plan (when you have enough information)

For each turn, respond with EXACTLY ONE of:

A) A question (JSON):
{
  "type": "question",
  "question": "clear question text in the form's language",
  "question_type": "single_choice | multiple_choice | free_text | confirm",
  "options": [{"id": "opt1", "label": "..."}],
  "context": "why you are asking this"
}

B) A fill plan (JSON):
{
  "type": "fill_plan",
  "filled_fields": [...],
  "unfilled_fields": [...],
  "warnings": [...]
}

Guidelines:
- Ask only the most impactful questions (3-5 max across all turns)
- Prioritize questions that resolve ambiguity for MANY fields at once
- When the user answers, use their answer to inform your next decision
- When you have enough info, return the fill plan — do not keep asking
- Use nearby_labels to understand what each field means
```

---

## Appendix B: Sequence Diagram

### Detailed Mode (adaptive, 2 questions)

```
User          Frontend         API (SSE)          FillPlanner (LLM)
 │               │                │                    │
 ├─ Click Run ──►│                │                    │
 │  (detailed)   ├─ POST stream ─►│                    │
 │               │  conv=[]       ├─ plan_turn() ─────►│
 │               │                │                    ├─ analyze context
 │               │                │◄── SSE: question ──┤
 │               │◄── question ───┤                    │
 │               │                │                    │
 │◄── modal Q1 ──┤                │                    │
 │               │                │                    │
 ├─ answer Q1 ──►│                │                    │
 │               ├─ POST stream ─►│                    │
 │               │  conv=[Q1,A1]  ├─ plan_turn() ─────►│
 │               │                │                    ├─ with Q1 answer
 │               │                │◄── SSE: question ──┤
 │               │◄── question ───┤                    │
 │               │                │                    │
 │◄── modal Q2 ──┤                │                    │
 │               │                │                    │
 ├─ answer Q2 ──►│                │                    │
 │               ├─ POST stream ─►│                    │
 │               │  conv=[Q1,A1,  ├─ plan_turn() ─────►│
 │               │   Q2,A2]       │                    ├─ enough info
 │               │                │◄── SSE: fill_plan ─┤
 │               │◄── fill_plan ──┤                    │
 │               │                │                    │
 │               ├─ render ──────►│                    │
 │               │◄── result ─────┤                    │
 │◄── results ───┤                │                    │
```
