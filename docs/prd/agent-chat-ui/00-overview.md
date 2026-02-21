# PRD: Agent-Driven Chat UI — Overview

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Overview

An **intelligent application form filling service** powered by a conversational AI agent. Users interact through a ChatGPT-style interface where the agent:

1. **Understands form rules** - Identifies required vs optional fields, validation rules, and form-specific logic
2. **Fills intelligently** - Knows which fields can be left blank, which need specific formats, and when to ask for clarification
3. **Generates from any input** - Accepts source documents, direct chat input, or a mix of both
4. **Remembers user data** - Saves profiles for returning users to speed up future forms
5. **Supports power users** - Batch processing and templates for generating multiple documents

This is NOT a data extraction service. The goal is to **help users complete application forms correctly**.

### User Types

| User Type | Primary Need | Key Features |
|-----------|--------------|--------------|
| Casual | Fill one form occasionally | Guided input, simple flow |
| Regular | Fill similar forms repeatedly | Saved profile, data reuse |
| Power User | Generate many documents | Templates, batch processing |

---

## Problem Statement

**Current State:**
- Users must manually understand which fields are required
- Forms have complex rules that users often get wrong
- Filling applications is tedious and error-prone
- Users must select a "mode" upfront, rigid workflow

**Desired State:**
- Agent understands form rules automatically
- Agent guides users through only what's needed
- Agent fills intelligently, skipping optional fields when appropriate
- Natural conversation flow adapts to user needs

---

## User Goals

**Primary Use Case:** User needs to complete an application form correctly and efficiently.

**Example Scenario:**
1. User uploads a government benefits application
2. Agent: "This form has 45 fields but only 12 are required. Some have rules - SSN format, income section only if employed. Want me to guide you through just the required fields?"
3. User: "Yes, guide me"
4. Agent: Asks for required fields one by one, skipping conditional sections that don't apply
5. Agent: "All required fields complete! 33 optional fields left blank. [Preview]"
6. User: "Looks good"
7. Agent: "[Download PDF]" - form is ready for submission
