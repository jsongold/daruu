# PRD: Agent-Driven Chat UI — Core Features

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Core Features

### 1. Chat Interface

**Layout:** Side-by-side
- Left panel: Document preview (zoomable, paginated)
- Right panel: Chat conversation

**Chat Input:**
- Text input at bottom (like ChatGPT)
- Drag & drop zone for documents
- Upload button for file picker
- Support for images, PDFs

**Message Types:**
| Type | Description |
|------|-------------|
| User message | Text or file upload |
| Agent thinking | "Analyzing your documents..." with spinner |
| Agent message | Explanation, question, or result |
| Approval request | Batch preview with Accept/Edit options |
| System message | Errors, status updates |

### 2. Agent Behavior

**Core Principles:**
- **Understand form rules first** - Identify required fields, validation rules, conditional logic
- **Fill smartly** - Only ask about fields that matter; skip truly optional fields
- **Show thinking, ask for approval** - Explain decisions before acting
- **Quick interactions** - Target: 1-5 turns for typical forms

**Agent Capabilities:**

| Capability | Description |
|------------|-------------|
| Rule Detection | Identifies required (*) fields, field types, format rules |
| Smart Defaults | Knows common patterns (date formats, phone formats, etc.) |
| Conditional Logic | Understands "if X, then fill Y" relationships |
| Optional Field Handling | Can skip optional fields or ask user preference |
| Validation | Checks values before filling (e.g., valid dates, SSN format) |

**Decision Flow:**
```
Upload Document(s)
    ↓
Agent analyzes form → Understands structure & rules
    ↓
"This form has 20 fields: 8 required, 12 optional"
    ↓
If source document provided:
    → Extract relevant data
    → Map to required fields
    → Ask about missing required fields
Else:
    → Ask for required field values
    → Offer to fill optional fields
    ↓
Shows preview with filled fields highlighted
    ↓
User approves or requests changes
    ↓
Agent generates filled PDF
    ↓
Save + Download
```

**Role Detection:**
- Agent auto-detects document roles (form vs source)
- Always asks user to confirm before proceeding
- Criteria: AcroForm fields = form, dense text/tables = source

**Field Handling Strategy:**

| Field Type | Agent Behavior |
|------------|----------------|
| Required (unfilled) | Must ask user or find in source |
| Required (found) | Fill and show in preview |
| Optional (found) | Fill, but note it's optional |
| Optional (not found) | Skip, don't ask unless user wants |
| Conditional | Only ask if condition is met |

### 3. Document Preview

**Features:**
- Page navigation
- Zoom controls
- Highlight active field being discussed
- Click-to-edit on form fields
- Side-by-side comparison (before/after)

**States:**
| State | Display |
|-------|---------|
| Uploaded | Original document |
| Analyzing | Document with scanning animation |
| Fields detected | Highlight form fields |
| Filled preview | Show proposed values |
| Final | Completed form |

### 4. Editing Values

**Two Methods:**

1. **Natural Language (Chat):**
   - "Change the name to John Smith"
   - "Update line 7 to $50,000"
   - "Clear the address field"

2. **Direct Edit (Click):**
   - Click on field in preview
   - Inline edit popover appears
   - Type new value, press Enter

### 5. Conversation History

**Sidebar:**
- List of past conversations
- Each entry shows: date, form name, status
- Click to resume or view completed job
- Search/filter capability

**Persistence:**
- Conversations saved to user account
- Filled PDFs stored and downloadable
- Can re-open and make edits
