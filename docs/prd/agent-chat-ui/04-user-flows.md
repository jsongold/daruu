# PRD: Agent-Driven Chat UI — User Flows

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

## User Flows

### Flow 1: Happy Path (2 documents)

```
┌─────────────────────────────────────────────────────────────┐
│ [Sidebar]          │  [Document Preview]  │  [Chat]         │
│                    │                      │                 │
│ + New Chat         │  (empty)             │  Welcome!       │
│                    │                      │  Drop files to  │
│ Today              │                      │  get started.   │
│ ─────────          │                      │                 │
│                    │                      │  ┌───────────┐  │
│                    │                      │  │  📎 Drop  │  │
│                    │                      │  │  files    │  │
│                    │                      │  └───────────┘  │
└─────────────────────────────────────────────────────────────┘

User drops 2 files: form.pdf, invoice.pdf

┌─────────────────────────────────────────────────────────────┐
│ [Sidebar]          │  [Document Preview]  │  [Chat]         │
│                    │  ┌──────────────┐    │                 │
│ + New Chat         │  │ form.pdf     │    │  User: 📎 2     │
│                    │  │  [Page 1/3]  │    │  files uploaded │
│ Today              │  │              │    │                 │
│ ─────────          │  │  [Fields     │    │  Agent:         │
│ ○ Tax form...      │  │   highlighted]│   │  I found:       │
│                    │  └──────────────┘    │  • form.pdf     │
│                    │                      │    (blank form) │
│                    │                      │  • invoice.pdf  │
│                    │                      │    (source doc) │
│                    │                      │                 │
│                    │                      │  Is this right? │
│                    │                      │  [Yes] [Switch] │
└─────────────────────────────────────────────────────────────┘

User clicks [Yes]

┌─────────────────────────────────────────────────────────────┐
│                    │  [Filled Preview]    │                 │
│                    │  ┌──────────────┐    │  Agent:         │
│                    │  │ form.pdf     │    │  Here's the     │
│                    │  │  [Page 1/3]  │    │  filled form.   │
│                    │  │              │    │                 │
│                    │  │  Name: [John]│    │  ┌───────────┐  │
│                    │  │  Total:[$500]│    │  │ Preview   │  │
│                    │  │  ...         │    │  │ Card      │  │
│                    │  └──────────────┘    │  │           │  │
│                    │                      │  │ [Approve] │  │
│                    │                      │  │ [Edit]    │  │
│                    │                      │  └───────────┘  │
└─────────────────────────────────────────────────────────────┘

User clicks [Approve]

┌─────────────────────────────────────────────────────────────┐
│                    │  [Final PDF]         │                 │
│                    │                      │  Agent:         │
│ Today              │                      │  Done! Your     │
│ ─────────          │                      │  form is ready. │
│ ● Tax form - Done  │                      │                 │
│                    │                      │  [Download PDF] │
│                    │                      │                 │
└─────────────────────────────────────────────────────────────┘
```

### Flow 2: With Edits

```
Agent shows preview...

User: "Change the address to 123 Main St"

Agent: "Updated the address. Here's the new preview."
       [Updated Preview Card]
       [Approve] [More Edits]

User clicks on a field in preview → inline editor appears

User types new value, presses Enter

Agent: "Got it. Updated [field name] to [value]."
```

### Flow 3: Single Document (Form Only)

```
User drops: blank_form.pdf

Agent: "I see a blank form with 15 fields.
        I don't see a source document.

        Would you like to:
        • Upload a source document
        • Fill the form manually via chat"

User: "I'll fill it manually"

Agent: "Great. Let's start with the first field:
        'Full Name' - What should I put here?"

User: "John Smith"

Agent: "Got it. Next field: 'Date of Birth'?"

... continues until form is filled ...
```
