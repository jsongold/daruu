# PRD: Agent-Driven Chat UI — Technical Architecture

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## Technical Architecture

### Agent System

**Hybrid LLM Approach:**

| Task | Model | Reason |
|------|-------|--------|
| Form Analysis | GPT-4o | Vision for understanding form structure, field labels, required markers |
| Rule Detection | Claude | Strong reasoning for conditional logic, validation rules |
| Data Extraction | GPT-4o | Vision for reading source documents |
| Conversation | Claude | Natural dialogue, asking clarifying questions |
| Validation | GPT-4o-mini | Fast format checking (SSN, dates, phone numbers) |

**Form Rule Understanding:**

The agent analyzes each form to understand:
1. **Required fields** - Marked with *, "required", or form-specific rules
2. **Field types** - Text, date, number, checkbox, dropdown
3. **Format rules** - SSN (XXX-XX-XXXX), phone, date format, etc.
4. **Conditional logic** - "If employed, fill income section"
5. **Field relationships** - "Spouse SSN required if Filing Status = Married"
6. **Common patterns** - Standard forms (W-9, 1040, I-9) have known rules

**Agent Loop:**
```python
class FormFillingAgent:
    async def process(self, message: UserMessage) -> AgentResponse:
        # 1. If new form uploaded, analyze structure and rules
        if has_new_form(message):
            self.form_rules = await self.analyze_form_rules(message.form)

        # 2. Determine what's still needed
        missing_required = self.get_missing_required_fields()

        # 3. If source docs provided, try to fill from them
        if has_source_docs(message):
            filled = await self.extract_and_fill(message.sources)
            missing_required = self.get_missing_required_fields()

        # 4. Ask user for remaining required fields
        if missing_required:
            return self.ask_for_field(missing_required[0])

        # 5. All required fields complete - show preview
        return self.show_preview()
```

### Pipeline Integration

**Current Stages (Hidden from User):**
- INGEST → STRUCTURE → LABELLING → MAP → EXTRACT → ADJUST → FILL → REVIEW

**Agent Abstraction:**
```
User sees:          Agent uses internally:
-----------         --------------------
"Analyzing..."  →   INGEST + STRUCTURE + LABELLING
"Mapping..."    →   MAP + EXTRACT
"Filling..."    →   ADJUST + FILL
"Reviewing..."  →   REVIEW
```

### API Changes

**New Endpoints:**

```
POST /api/v1/conversations
  → Create new conversation

POST /api/v1/conversations/{id}/messages
  → Send message (text or file)

GET /api/v1/conversations/{id}/messages
  → Get conversation history

GET /api/v1/conversations
  → List user's conversations

POST /api/v1/conversations/{id}/approve
  → Approve current preview

POST /api/v1/conversations/{id}/download
  → Download filled PDF
```

**Remove:**
- Mode selection from job creation
- Explicit stage endpoints

### Frontend Components

```
src/
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx      # Main layout
│   │   ├── MessageList.tsx        # Conversation display
│   │   ├── MessageInput.tsx       # Input with drag-drop
│   │   ├── AgentMessage.tsx       # Agent response bubble
│   │   ├── UserMessage.tsx        # User message bubble
│   │   ├── ApprovalCard.tsx       # Preview + approve/edit
│   │   └── ThinkingIndicator.tsx  # Loading state
│   │
│   ├── preview/
│   │   ├── DocumentPreview.tsx    # PDF viewer
│   │   ├── FieldHighlight.tsx     # Highlight active field
│   │   ├── InlineEditor.tsx       # Click-to-edit popover
│   │   └── ZoomControls.tsx
│   │
│   └── sidebar/
│       ├── ConversationList.tsx   # History sidebar
│       └── ConversationItem.tsx
│
├── hooks/
│   ├── useConversation.ts         # Conversation state
│   ├── useAgent.ts                # Agent communication
│   └── useDocumentPreview.ts
│
└── pages/
    └── ChatPage.tsx               # Main page
```
