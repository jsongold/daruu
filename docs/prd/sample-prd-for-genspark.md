# Sample PRD: Chat-Based Reading List Curator

> **Purpose:** Example PRD for prompting (e.g. Genspark). ~10% size of a full PRD. Core concept changed to avoid leaking the actual product idea.

---

## Overview

A **chat-based reading list assistant** that helps users collect and organize what they want to read. Users talk in a ChatGPT-style UI; the agent suggests titles, saves preferences, and outputs a simple list.

**Value:**
1. **Understands intent** – Picks up genres, topics, and “read later” from natural chat.
2. **Curates smartly** – Suggests based on past likes and explicit preferences.
3. **Accepts mixed input** – Links, pasted text, or voice-style descriptions.
4. **Remembers preferences** – Saves a lightweight profile for returning users.
5. **Supports power users** – Export list, tags, and filters.

Goal: **help users build and maintain a personal reading list with minimal effort**.

### User Types

| Type       | Need                     | Features              |
|-----------|---------------------------|------------------------|
| Casual    | Occasional “save for later” | Simple add + list      |
| Regular   | Ongoing list across devices | Profile, sync          |
| Power user| Many items, organized     | Tags, export, filters   |

---

## Problem & Goals

**Current:** Users juggle links, notes, and apps; lists get scattered and forgotten.

**Desired:** One chat where users say what they want to read; the agent maintains the list and suggests next steps.

**Primary use case:** User wants one place to capture “want to read” items and get a manageable list (and optional export).

**Example flow:**
1. User: “Add that article about habits from the link I sent yesterday.”
2. Agent finds the link, adds it, and asks: “Tag as ‘self-help’?”
3. User: “Yes. What should I read next from my list?”
4. Agent suggests 1–2 items and shows the list. User can export as text or PDF.

---

## Core Features (Condensed)

### 1. Chat UI

- **Layout:** Single main area: chat thread + input (no side-by-side panels in v1).
- **Input:** Text + paste links; optional “attach” for screenshots or notes.
- **Message types:** User, Agent (reply/suggestion), System (errors/status).

### 2. Agent Behavior

- **Principles:** Infer intent from chat; suggest, don’t overwhelm; ask only when it disambiguates.
- **Capabilities:** Add/remove items, tag, suggest “next read,” summarize list, export (e.g. text/PDF).
- **Flow:** User message → Agent interprets → Update list / suggest / ask one short question → Reply.

### 3. List & Export

- **List:** Stored per user; fields: title, source (link/note), tags, added date.
- **Export:** “Send my list” → plain text or PDF (simple layout).

### 4. User Profile (Minimal)

- **Stored:** Preferred genres, last N items, export preference (text vs PDF). No PII beyond what user says in chat.

---

## Out of Scope (Sample)

- No real-time collaboration.
- No integration with ebook stores or libraries.
- No recommendations from external APIs (only from user’s own list and stated preferences).
- No offline mode.

---

## Success Metrics

| Metric              | Target   |
|---------------------|----------|
| Items added per session | ≥ 2      |
| Export used (e.g. once/month) | > 20% users |
| Conversation length  | &lt; 6 turns to add + get suggestion |

---

## Tech Stack (Illustrative)

- **Backend:** REST API, auth, single “conversation” or thread per user, list stored in DB.
- **Agent:** LLM for intent + list actions; no complex pipeline.
- **Frontend:** Chat UI (e.g. Vercel AI SDK or similar), minimal state.

---

## Implementation Phases (Sketch)

| Phase | Goal                          |
|-------|-------------------------------|
| 0     | Auth + chat UI + “echo” agent |
| 1     | Add/list/remove items via chat, persist list |
| 2     | Suggest “next read,” tags, export to text/PDF |
| 3     | Profile, preferences, basic analytics       |

---

*This is a shortened, concept-shifted sample for prompt engineering. It is not the real product PRD.*
