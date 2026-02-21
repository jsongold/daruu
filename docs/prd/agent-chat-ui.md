# PRD: Agent-Driven Chat UI for Form Filling

> **Split by concern:** This PRD is also split into focused documents under [docs/prd/agent-chat-ui/](agent-chat-ui/). See [agent-chat-ui/README.md](agent-chat-ui/README.md) for the index.

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

---

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

---

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

---

## Data Models

### Conversation

```typescript
interface Conversation {
  id: string
  userId: string
  status: 'active' | 'completed' | 'abandoned'
  createdAt: string
  updatedAt: string

  // Documents in this conversation
  documents: Document[]

  // Current state
  formDocumentId?: string
  sourceDocumentIds: string[]
  filledPdfRef?: string

  // Metadata
  title?: string  // Auto-generated or user-set
}
```

### Message

```typescript
interface Message {
  id: string
  conversationId: string
  role: 'user' | 'agent' | 'system'
  content: string

  // For file uploads
  attachments?: Attachment[]

  // For agent messages
  thinking?: string           // Internal reasoning (optional to show)
  previewRef?: string         // Link to preview image/PDF
  approvalRequired?: boolean

  createdAt: string
}

interface Attachment {
  id: string
  filename: string
  contentType: string
  ref: string  // Storage reference
}
```

### Agent State

```typescript
interface AgentState {
  conversationId: string

  // What the agent knows
  documents: DetectedDocument[]
  formFields: Field[]
  extractedValues: ExtractedValue[]

  // Current progress
  currentStage: 'analyzing' | 'confirming' | 'mapping' | 'filling' | 'reviewing' | 'complete'

  // Pending questions
  pendingQuestions: Question[]
}

interface DetectedDocument {
  documentId: string
  detectedRole: 'form' | 'source' | 'unknown'
  confidence: number
  confirmedByUser: boolean
}
```

### User Profile (For Returning Users)

```typescript
interface UserProfile {
  id: string
  userId: string

  // Common personal information
  fullName?: string
  email?: string
  phone?: string
  dateOfBirth?: string
  ssn?: string  // Encrypted, last 4 shown

  // Address
  address?: {
    street: string
    city: string
    state: string
    zip: string
  }

  // Employment
  employer?: string
  jobTitle?: string
  income?: number

  // Usage
  lastUsed: string
  createdAt: string
  updatedAt: string
}
```

### Batch Job (For Power Users)

```typescript
interface BatchJob {
  id: string
  conversationId: string
  userId: string

  // Template
  templateDocumentId: string
  templateFields: string[]  // Fields to fill for each item

  // Items to process
  items: BatchItem[]
  status: 'pending' | 'processing' | 'completed' | 'failed'

  // Output
  outputRefs: string[]  // Array of filled PDF refs

  createdAt: string
  completedAt?: string
}

interface BatchItem {
  index: number
  values: Record<string, string>  // fieldName -> value
  status: 'pending' | 'completed' | 'failed'
  outputRef?: string
  error?: string
}
```

---

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

---

## Validation Scenarios

> **Note:** The scenarios below were written for an earlier conversational approach.
> The **actual implementation** follows the "Auto-fill first" philosophy:
> 1. User uploads documents
> 2. Agent auto-fills ALL fields without asking questions
> 3. User sees filled preview immediately
> 4. User edits via inline or chat if needed
> 5. User downloads
>
> These scenarios remain for edge case coverage but agent behavior is NON-CONVERSATIONAL.

### Common Cases (Happy Paths)

#### Scenario 1: Government Application with Complex Rules
**Context:** User needs to fill a government benefits application form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `benefits_application.pdf` | "I analyzed this benefits application form. It has **45 fields**: 12 required, 33 optional. Some fields have rules: - SSN must be XXX-XX-XXXX format - Date of Birth determines eligibility - Income section only required if employed. Do you have source documents, or shall I guide you through the required fields?" |
| 2 | "Guide me through it" | "Let's start with the required fields. **Full Legal Name** (required):" |
| 3 | "John Michael Smith" | "Got it. **Social Security Number** (required, format: XXX-XX-XXXX):" |
| 4 | "123-45-6789" | "Valid SSN. **Date of Birth** (required):" |
| 5 | "March 15, 1985" | "You're 39 years old - eligible for this program. **Current Employment Status** (required):" |
| 6 | "Unemployed" | "Since you're unemployed, I'm skipping the Income section (not required). **Current Address** (required):" |
| 7 | ... (continues for required fields only) | ... |
| 8 | (last required field) | "All 12 required fields complete! The 33 optional fields are left blank (you can fill them later if needed). [Preview] [Approve] [Add Optional Fields]" |

**Validates:** Rule detection, conditional logic, required vs optional handling, format validation.

---

#### Scenario 2: Tax Form with Source Document
**Context:** User has a tax form and a W-2.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `1040.pdf` and `w2.pdf` | "I found: - `1040.pdf`: Tax return form (23 fields, 15 required) - `w2.pdf`: W-2 showing wages of $75,000 from TechCorp Inc. I can auto-fill 10 of the 15 required fields from your W-2. The remaining 5 required fields need your input. Proceed?" |
| 2 | "Yes" | "Filled from W-2: Wages, Employer, EIN, Federal Tax Withheld, etc. Now I need: **Filing Status** (required - Single, Married Filing Jointly, etc.):" |
| 3 | "Married filing jointly" | "Got it. **Spouse's SSN** (required when married):" |
| 4 | "987-65-4321" | "**Number of Dependents** (required):" |
| 5 | "2" | "**Dependent Names and SSNs** (required when dependents > 0):" |
| 6 | "Emma Smith 111-22-3333, Jack Smith 444-55-6666" | "All required fields complete! [Preview] I left optional fields blank (charitable contributions, itemized deductions, etc.). Want to add any?" |
| 7 | "No, that's fine" | "[Download PDF]" |

**Validates:** Source document extraction, conditional required fields, smart field skipping.

---

#### Scenario 3: Simple Application (Few Required Fields)
**Context:** User has a membership application where most fields are optional.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `membership_form.pdf` | "This membership form has 15 fields but only **3 are required**: Name, Email, and Signature Date. The rest (phone, address, interests, referral source, etc.) are optional. Want to fill just the required fields, or all of them?" |
| 2 | "Just required" | "**Full Name** (required):" |
| 3 | "Sarah Johnson" | "**Email** (required):" |
| 4 | "sarah@email.com" | "**Today's Date** for signature (required) - I'll use January 30, 2024. OK?" |
| 5 | "Yes" | "Done! Only 3 fields filled, 12 left blank (all optional). [Preview] [Download]" |

**Validates:** Minimal interaction for simple forms, clear required/optional distinction.

---

#### Scenario 4: Chat-Based Form Filling (No Document Upload)
**Context:** User describes what they need via chat, agent generates the filled form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "I need to fill out a W-9 form for my freelance work" | "I can help you fill a W-9 form. I'll ask for the required information: **Legal Name** (as shown on your tax return):" |
| 2 | "Sarah Johnson" | "**Business Name** (if different from above, or leave blank):" |
| 3 | "Leave it blank" | "**Tax Classification** (Individual, LLC, Corporation, etc.):" |
| 4 | "Individual" | "**Address** (number, street, apt):" |
| 5 | "123 Main St, Apt 4B" | "**City, State, ZIP**:" |
| 6 | "New York, NY 10001" | "**SSN or EIN** (for tax identification):" |
| 7 | "123-45-6789" | "All required fields complete! Generating your W-9... [Preview] The signature and date fields are left for you to sign by hand. [Download PDF]" |

**Validates:** No source document needed, agent knows form structure, guided input.

---

#### Scenario 5: Multiple Source Documents
**Context:** User has a loan application and multiple supporting documents.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `loan_app.pdf`, `paystub.pdf`, `bank_stmt.pdf`, `tax_return.pdf` | "I found a loan application and 3 source documents. Let me analyze... - **Loan Application**: 35 fields, 18 required - **Paystub**: Monthly income $6,500, Employer: TechCorp - **Bank Statement**: Balance $24,000, Account ending 1234 - **Tax Return**: 2023 AGI $78,000. I can auto-fill 15 of 18 required fields. Proceed?" |
| 2 | "Yes" | "Filled: Income ($6,500/mo), Employer (TechCorp), Assets ($24,000), Annual Income ($78,000 from tax return). **3 required fields need your input**: Loan Amount, Loan Purpose, Co-Applicant (Yes/No):" |
| 3 | "$50,000 for home renovation, no co-applicant" | "Perfect. All required fields complete! [Preview] Optional fields left blank: Previous Addresses, Additional Income Sources, References. Add any?" |
| 4 | "No" | "[Download PDF]" |

**Validates:** Multi-document aggregation, intelligent field mapping, minimal user input.

---

#### Scenario 6: Generate Document from User Input Only
**Context:** User wants to fill a form purely from chat, no documents uploaded.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "I need to create an invoice for my client" | "I'll help you create an invoice. I need some information: **Your Business Name**:" |
| 2 | "Smith Consulting" | "**Client Name**:" |
| 3 | "Acme Corporation" | "**Invoice Items** (describe each service/product with amount):" |
| 4 | "Web design $2,000, Logo design $500" | "**Payment Terms** (due date or net days):" |
| 5 | "Net 30" | "**Your Contact Info** (for the invoice header):" |
| 6 | "john@smithconsulting.com, 555-1234" | "Here's your invoice: - Smith Consulting → Acme Corporation - Web design: $2,000 - Logo design: $500 - **Total: $2,500** - Due: 30 days from today [Preview] [Download PDF]" |

**Validates:** Pure chat-based document generation, no form upload required.

---

#### Scenario 7: Batch Processing with Template (Power User)
**Context:** HR user needs to generate the same form for multiple employees.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `offer_letter_template.pdf` | "I see an offer letter template with fields: Employee Name, Position, Salary, Start Date, Manager Name. Would you like to: (1) Fill for one person, or (2) **Batch fill** for multiple people?" |
| 2 | "Batch fill for 3 people" | "Great! I'll collect info for each person. **Person 1 - Employee Name**:" |
| 3 | "Alice Johnson" | "**Position**:" |
| 4 | "Software Engineer" | "**Salary**:" |
| 5 | "$120,000" | "**Start Date**:" |
| 6 | "Feb 15, 2024" | "**Manager Name**:" |
| 7 | "Bob Smith" | "Person 1 complete! **Person 2 - Employee Name**:" |
| 8 | ... (repeats for persons 2 and 3) | ... |
| 9 | (all 3 complete) | "3 offer letters ready: - Alice Johnson - Software Engineer - $120k - Carol Davis - Product Manager - $140k - David Lee - Designer - $100k. [Download All as ZIP] [Download Individual PDFs]" |

**Validates:** Template reuse, batch processing, multiple output files.

---

#### Scenario 8: Reuse Previous Data (Saved Profile)
**Context:** Returning user who has filled similar forms before.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops new `rental_application.pdf` | "I see a rental application. I notice you've filled similar forms before. Your saved info: - Name: John Smith - SSN: XXX-XX-6789 - Current Address: 123 Main St - Employer: TechCorp. **Use this saved data?**" |
| 2 | "Yes, but update address to 456 Oak Ave" | "Got it! Using saved profile with new address. Filling form... The form also asks for **Monthly Income** and **Landlord Reference** - not in your profile. **Monthly Income**:" |
| 3 | "$6,500" | "**Landlord Reference** (name and phone):" |
| 4 | "Jane Doe, 555-9876" | "All fields complete! [Preview] Your profile has been updated with new address. [Download PDF]" |

**Validates:** Profile/data reuse, incremental updates, returning user experience.

---

### Complex Form Scenarios

#### Complex 1: Multi-Page Form with Sections
**Context:** User has a 10-page insurance application with different sections.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `insurance_app.pdf` (10 pages) | "This is a 10-page insurance application with 4 sections: - **Section A (Pages 1-3):** Personal Info - 12 fields, 8 required - **Section B (Pages 4-5):** Health History - 15 fields, 10 required - **Section C (Pages 6-8):** Coverage Selection - 8 fields, 5 required - **Section D (Pages 9-10):** Signatures & Declarations. Want to fill section by section, or all at once?" |
| 2 | "Section by section" | "Starting with **Section A: Personal Info**. **Full Legal Name** (required):" |
| 3 | "John Michael Smith" | "**Date of Birth** (required):" |
| 4 | ... (continues through section A) | "Section A complete! Moving to **Section B: Health History**. Do you have any pre-existing conditions? (Yes/No):" |
| 5 | "No" | "Great - I'm skipping the detailed health questions since you answered No. **Section B complete!** Moving to **Section C: Coverage Selection**..." |
| 6 | ... (completes all sections) | "All 4 sections complete! [Preview All Pages] [Preview by Section] [Download PDF]" |

**Validates:** Multi-page navigation, section-based filling, conditional section skipping.

---

#### Complex 2: Form Requiring Attachments
**Context:** Visa application that requires photo and supporting documents.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `visa_application.pdf` | "This visa application requires: - Personal information fields - **Passport photo** (required attachment) - **Flight itinerary** (required attachment) - **Hotel booking** (optional attachment). Do you have these documents ready?" |
| 2 | "Yes" | "Let's fill the form first, then add attachments. **Full Name as shown on passport**:" |
| 3 | ... (fills form fields) | "Form fields complete! Now let's add the required attachments. **Upload your passport photo** (JPEG or PNG, max 5MB):" |
| 4 | Drops `passport_photo.jpg` | "Photo uploaded ✓. Checking requirements... ✓ Face visible, ✓ Correct dimensions. **Upload flight itinerary** (PDF):" |
| 5 | Drops `flight.pdf` | "Itinerary uploaded ✓. I see: Flight to Paris on March 15, return March 22. **Hotel booking** (optional - skip or upload):" |
| 6 | "Skip" | "All done! Your application package includes: - Filled visa form (3 pages) - Passport photo - Flight itinerary. [Preview Package] [Download as ZIP]" |

**Validates:** Attachment handling, file validation, package generation.

---

#### Complex 3: Form with Digital Signature
**Context:** Contract that requires electronic signature.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `contract.pdf` | "This contract has 2 pages with: - Party details (your info) - Terms (pre-filled) - **Signature field** - **Date field**. Would you like to fill and sign electronically?" |
| 2 | "Yes" | "**Your Full Legal Name** (as it will appear in signature):" |
| 3 | "Sarah Johnson" | "**Your Title/Role**:" |
| 4 | "CEO, Johnson Consulting" | "All fields filled. For your signature, choose a method: [Type Name] [Draw Signature] [Upload Image]" |
| 5 | Clicks [Type Name] | "Signature style: [Script] [Print] [Formal]. Preview: *Sarah Johnson*" |
| 6 | Selects [Script] | "Signature applied! Date auto-filled: January 30, 2024. [Preview Signed Contract] [Download PDF]" |

**Validates:** Signature fields, multiple signature methods, date auto-fill.

---

#### Complex 4: Form with Calculations
**Context:** Expense report that requires totals and tax calculations.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `expense_report.pdf` | "This expense report has calculation fields. I'll compute totals automatically. **Trip Purpose** (required):" |
| 2 | "Client meeting in NYC" | "**Expense items** - tell me each expense (description, amount, category):" |
| 3 | "Flight $450, Hotel 2 nights $300, Meals $85, Uber $45" | "I've entered: | Item | Amount | Category | |------|--------|----------| | Flight | $450 | Travel | | Hotel (2 nights) | $300 | Lodging | | Meals | $85 | Meals | | Uber | $45 | Transport | **Subtotal: $880** Add more expenses or continue?" |
| 4 | "That's all" | "Calculating totals: - Subtotal: $880.00 - Tax (if applicable): Meals taxable → $7.65 - **Total Reimbursement: $887.65** [Preview] [Download]" |

**Validates:** Auto-calculation, itemized entry, tax rules.

---

#### Complex 5: Form with Conditional Pages
**Context:** Business license application where pages depend on business type.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `business_license.pdf` (15 pages) | "This business license application has conditional sections. Some pages only apply to certain business types. **Business Type** (this determines which sections you need):" |
| 2 | "Restaurant" | "For a Restaurant, you need: - Pages 1-3: Basic Business Info (all businesses) - Pages 4-5: ~~Corporation Info~~ (skipped - not applicable) - Pages 6-7: **Food Service License** (required for restaurants) - Pages 8-9: **Health & Safety Compliance** (required for restaurants) - Pages 10-12: ~~Retail Sales~~ (skipped) - Pages 13-15: Signatures. You'll fill 9 of 15 pages. Ready to start?" |
| 3 | "Yes" | "**Business Name** (required):" |
| 4 | ... (fills applicable sections) | "Applicable sections complete! I've left pages 4-5 and 10-12 blank (not required for restaurants). [Preview Applicable Pages] [Preview All] [Download]" |

**Validates:** Conditional page logic, dynamic form sections, clear skip explanations.

---

#### Complex 6: Non-AcroForm PDF (Scanned/Flat Form)
**Context:** User uploads a PDF that has no interactive form fields - just a scanned image of a form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `scanned_form.pdf` | "This PDF doesn't have interactive form fields (it's a scanned or flat document). I'll analyze the form layout to find where text should go... Found **12 fillable areas**: Name, Address, Date, etc. I'll place your text in the correct positions. Ready to fill?" |
| 2 | "Yes" | "**Name** (I'll place this in the box at the top left):" |
| 3 | "John Smith" | "**Address** (large box below name):" |
| 4 | ... (continues) | "All fields identified and filled! [Preview] I've overlaid your text on the original form. Text positioning: ✓ All fields placed correctly. [Download PDF]" |

**Validates:** Bbox detection, text overlay positioning, non-AcroForm handling.

**Technical Note:** Agent uses vision LLM to:
1. Identify form field locations (bounding boxes)
2. Determine field types (text, checkbox, date)
3. Calculate text placement coordinates
4. Generate PDF with text overlay at correct positions

---

#### Complex 7: Image as Form (JPG/PNG)
**Context:** User uploads an image file (not PDF) of a form they need to fill.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `form_photo.jpg` (photo of a paper form) | "I see an image of a form. I'll analyze it to find the fillable areas... Found **8 fields**: Name, ID Number, Signature, etc. I'll create a filled PDF from this image. Ready?" |
| 2 | "Yes" | "**Name** (line at top):" |
| 3 | "Maria Garcia" | "**ID Number** (box in upper right):" |
| 4 | ... (continues) | "All fields filled! I've created a PDF with the original form image and your text overlaid. [Preview] [Download PDF]" |

**Validates:** Image input handling, image-to-PDF conversion, bbox detection on images.

---

#### Complex 8: Mixed Documents (Image Source + PDF Form)
**Context:** User has a PDF form and an image (photo of a receipt) as source.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `expense_form.pdf` and `receipt_photo.jpg` | "I found: - `expense_form.pdf`: Expense report form (AcroForm with 10 fields) - `receipt_photo.jpg`: Photo of a receipt. Let me read the receipt... Found: Store: Office Depot, Amount: $47.83, Date: Jan 28, 2024. Fill the expense form with this data?" |
| 2 | "Yes" | "Filled from receipt: Vendor = Office Depot, Amount = $47.83, Date = Jan 28, 2024. **Expense Category** (not on receipt):" |
| 3 | "Office Supplies" | "All fields complete! [Preview] [Download]" |

**Validates:** Image as source document, OCR on images, mixed document types.

---

### Edge Cases

#### Edge Case 1: Conflicting Data from Multiple Sources
**Context:** Two source documents have different values for the same field.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops form + two paystubs with different employers | "I found conflicting information: - Paystub 1 (Jan 2024): Employer = TechCorp, Income = $6,000 - Paystub 2 (Feb 2024): Employer = DataInc, Income = $6,500. Which employer should I use, or did you change jobs?" |
| 2 | "I changed jobs in February, use DataInc" | "Got it! Using DataInc as current employer with $6,500 income. [Continues filling...]" |

**Validates:** Conflict detection, user resolution, context-aware questions.

---

#### Edge Case 2: Invalid Format Correction
**Context:** User provides data in wrong format.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Agent asks for SSN | |
| 2 | "123456789" | "That doesn't match the required format (XXX-XX-XXXX). Did you mean **123-45-6789**?" |
| 3 | "Yes" | "Got it. [Continues to next field...]" |

**Validates:** Format validation, helpful correction, not blocking on minor issues.

---

#### Edge Case 3: Unknown Form Type
**Context:** Agent encounters a form it hasn't seen before.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops unusual government form | "I found a form with 28 fields. I don't recognize this specific form type, so I can't determine which fields are required by regulation. I'll treat fields marked with (*) as required and others as optional. I found 10 fields marked required. Proceed?" |
| 2 | "Yes" | "**Field 1: Applicant Name** (marked required):" |

**Validates:** Graceful handling of unknown forms, falls back to visual cues.

---

#### Edge Case 4: Partial Extraction from Poor Quality Scan
**Context:** Source document is blurry/low quality.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Uploads form and blurry scanned W-2 | "I had trouble reading parts of your W-2. Here's what I found: - Wages: $75,??? (last 3 digits unclear) - Employer: Tech[???] Corp - SSN: Clear ✓. Can you confirm the wages amount and employer name?" |
| 2 | "$75,432 from TechData Corp" | "Thanks! Filling with corrected values. [Preview]" |

**Validates:** Confidence indicators, partial extraction, user correction.

---

### Scope-Out Cases (Explicitly NOT Supported)

#### Out of Scope 1: Form Creation/Design
**Context:** User wants to create a new form, not fill an existing one.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "Create a new invoice template for me" | "I help fill existing forms, not create new ones. If you have a blank invoice PDF, I can help you fill it out. For creating new forms, try tools like Adobe Acrobat or JotForm." |

**Why Out of Scope:** Form creation is a different product. Focus on filling existing forms well.

---

#### Out of Scope 2: Non-PDF/Non-Image Files
**Context:** User tries to upload unsupported file types.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops `spreadsheet.xlsx` | "I work with PDF and image files (PNG, JPG, TIFF) only. Please export your spreadsheet as a PDF first, then upload it." |

**Why Out of Scope:** Focus on PDF and images. Office document parsing adds complexity.

**Note:** Images ARE supported as both source documents and as forms to fill.

---

#### Out of Scope 3: Real-Time Collaboration
**Context:** User wants multiple people to fill the same form simultaneously.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "Can my colleague edit this form with me at the same time?" | "Each conversation is for one person. If you need someone to review, download the preview and share it, then come back to make changes." |

**Why Out of Scope:** Real-time collaboration requires significant infrastructure (CRDTs, websockets). Phase 1 focuses on single-user experience.

---

#### Out of Scope 4: Form Submission to Government/Third Parties
**Context:** User expects the app to submit the form directly to a government agency.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "Submit this form to the IRS for me" | "I help you fill forms, but I can't submit them to external agencies. Download your completed form and submit it through the official channels (mail, online portal, etc.)." |

**Why Out of Scope:** Legal/compliance risk, API integrations with government systems are complex and vary by jurisdiction.

---

#### Out of Scope 5: Handwriting Recognition on Printed Forms
**Context:** User uploads a photo of a handwritten form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | Drops photo of handwritten form | "I can read typed/printed text and digital forms, but handwritten text is difficult to interpret accurately. Please use a blank digital form, or type the information to me directly." |

**Why Out of Scope:** Handwriting OCR is unreliable, especially for important documents. Risk of errors is too high.

---

#### Out of Scope 6: Legal/Medical Advice
**Context:** User asks for guidance on what to put in a legal or medical form.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | "What should I put for my medical history?" | "I can help you fill out the form, but I can't provide medical or legal advice. Please consult with a doctor or lawyer for guidance on what to enter, then tell me the values." |
| 2 | "Is this tax deduction legal?" | "I'm not qualified to give tax advice. Please consult a tax professional. Once you know what values to use, I'll help you fill the form correctly." |

**Why Out of Scope:** Legal liability, professional licensing requirements, accuracy concerns.

---

#### Out of Scope 7: Offline Mode
**Context:** User wants to use the app without internet.

| Step | User Action | Agent Response |
|------|-------------|----------------|
| 1 | (No internet connection) | "I need an internet connection to analyze forms and provide assistance. Please reconnect and try again." |

**Why Out of Scope:** AI processing requires cloud infrastructure. Offline would require completely different architecture.

---

### Scope-Out Summary

| Feature | Status | Alternative |
|---------|--------|-------------|
| Form creation | ❌ Out | Use Adobe Acrobat, JotForm |
| Non-PDF/Image files | ❌ Out | Export to PDF first |
| Real-time collaboration | ❌ Out | Share preview, make changes sequentially |
| Form submission | ❌ Out | Download and submit manually |
| Handwriting recognition | ❌ Out | Use digital forms or type values |
| Legal/medical advice | ❌ Out | Consult professionals |
| Offline mode | ❌ Out | Requires internet |

### IN Scope: Special Handling

| Feature | Status | How It Works |
|---------|--------|--------------|
| Image files (PNG, JPG, TIFF) | ✅ In | Treated as single-page documents, can be form or source |
| Non-AcroForm PDFs | ✅ In | LLM detects field locations, generates bounding boxes |
| Scanned forms | ✅ In | OCR + bbox generation for text placement |

---

### Scenario Coverage Matrix

| Scenario | AcroForm | Non-AcroForm | Image | Bbox Gen | OCR |
|----------|----------|--------------|-------|----------|-----|
| Government App | ✓ | | | | |
| Tax Form + W-2 | ✓ | | | | |
| Simple Membership | ✓ | | | | |
| Chat-Based (W-9) | ✓ | | | | |
| Multiple Sources | ✓ | | | | |
| Generate from Chat | ✓ | | | | |
| Batch Template | ✓ | | | | |
| Reuse Profile | ✓ | | | | |
| Multi-Page Sections | ✓ | | | | |
| Form + Attachments | ✓ | | | | |
| Digital Signature | ✓ | | | | |
| Calculations | ✓ | | | | |
| Conditional Pages | ✓ | | | | |
| **Non-AcroForm PDF** | | ✓ | | ✓ | ✓ |
| **Image as Form** | | | ✓ | ✓ | ✓ |
| **Mixed (Image Source)** | ✓ | | ✓ | | ✓ |

### Feature Coverage Summary

| Feature | Scenarios Covering It |
|---------|----------------------|
| AcroForm PDFs | 13 scenarios |
| Non-AcroForm PDFs (flat/scanned) | 1 scenario |
| Image files as form | 1 scenario |
| Image files as source | 1 scenario |
| Bounding Box Generation | 2 scenarios |
| OCR | 3 scenarios |
| Rule Detection | 9 scenarios |
| Required/Optional Fields | 8 scenarios |
| Multi-Page Forms | 4 scenarios |
| Attachments | 1 scenario |
| Digital Signature | 2 scenarios |
| Auto-Calculations | 2 scenarios |
| Conditional Logic | 4 scenarios |
| Batch Processing | 1 scenario |
| User Profile | 1 scenario |
| Source Document Extraction | 5 scenarios |

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
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

---

## Technical Details

### Database Schema (Supabase)

```sql
-- ============================================
-- CONVERSATIONS TABLE
-- ============================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Status tracking
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'abandoned', 'error')),

    -- Document references (after role detection)
    form_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    source_document_ids UUID[] DEFAULT '{}',

    -- Output
    filled_pdf_ref TEXT,  -- supabase:// URL to filled PDF

    -- Metadata
    title TEXT,  -- Auto-generated: "Tax Form - Jan 30"

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for listing user's conversations
CREATE INDEX idx_conversations_user_status
    ON conversations(user_id, status, created_at DESC);

-- ============================================
-- MESSAGES TABLE
-- ============================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,

    -- Message content
    role TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    content TEXT NOT NULL,

    -- Agent-specific fields
    thinking TEXT,              -- Internal reasoning (optional to show)
    preview_ref TEXT,           -- supabase:// URL to preview image
    approval_required BOOLEAN DEFAULT FALSE,
    approval_status TEXT CHECK (approval_status IN ('pending', 'approved', 'rejected', 'edited')),

    -- Metadata
    metadata JSONB DEFAULT '{}',  -- Flexible storage for actions, buttons, etc.

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fetching conversation messages
CREATE INDEX idx_messages_conversation
    ON messages(conversation_id, created_at ASC);

-- ============================================
-- MESSAGE ATTACHMENTS TABLE
-- ============================================
CREATE TABLE message_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,

    -- File info
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER,

    -- Storage reference
    ref TEXT NOT NULL,  -- supabase:// URL

    -- Link to document if processed
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_attachments_message ON message_attachments(message_id);

-- ============================================
-- AGENT STATE (cached in Redis, persisted here)
-- ============================================
CREATE TABLE agent_states (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,

    -- Agent's understanding
    detected_documents JSONB DEFAULT '[]',
    form_fields JSONB DEFAULT '[]',
    extracted_values JSONB DEFAULT '[]',

    -- Progress
    current_stage TEXT NOT NULL DEFAULT 'idle'
        CHECK (current_stage IN ('idle', 'analyzing', 'confirming', 'mapping', 'filling', 'reviewing', 'complete', 'error')),

    -- Pending questions for user
    pending_questions JSONB DEFAULT '[]',

    -- Error tracking
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================
-- TRIGGERS
-- ============================================
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at = NOW()
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_message_update_conversation
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION update_conversation_timestamp();
```

### Redis Schema (Agent State)

```
# Active agent state (fast access during conversation)
agent:state:{conversation_id} = {
    "conversation_id": "uuid",
    "current_stage": "analyzing",
    "detected_documents": [...],
    "form_fields": [...],
    "extracted_values": [...],
    "pending_questions": [...],
    "last_activity": "2024-01-30T12:00:00Z"
}
TTL: 1 hour (extended on activity)

# SSE connection registry
sse:connections:{conversation_id} = ["connection_id_1", "connection_id_2"]
TTL: 5 minutes (heartbeat refreshes)

# Rate limiting
rate:messages:{user_id} = count
TTL: 1 minute
Max: 30 messages/minute
```

### API Contracts

```yaml
openapi: 3.0.0
info:
  title: Agent Chat API
  version: 2.0.0

paths:
  /api/v2/conversations:
    post:
      summary: Create a new conversation
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                title:
                  type: string
                  description: Optional title (auto-generated if not provided)
      responses:
        '201':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Conversation'

    get:
      summary: List user's conversations
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [active, completed, all]
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
        - name: cursor
          in: query
          schema:
            type: string
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/ConversationSummary'
                  next_cursor:
                    type: string

  /api/v2/conversations/{id}:
    get:
      summary: Get conversation with recent messages
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ConversationWithMessages'

    delete:
      summary: Delete/abandon a conversation
      responses:
        '204':
          description: Deleted

  /api/v2/conversations/{id}/messages:
    post:
      summary: Send a message (text or file upload)
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                content:
                  type: string
                  description: Text message content
                files:
                  type: array
                  items:
                    type: string
                    format: binary
                  maxItems: 5
      responses:
        '202':
          description: Message accepted, agent processing
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Message'

    get:
      summary: Get messages (paginated)
      parameters:
        - name: before
          in: query
          schema:
            type: string
            format: uuid
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/Message'
                  has_more:
                    type: boolean

  /api/v2/conversations/{id}/stream:
    get:
      summary: SSE stream for real-time updates
      responses:
        '200':
          description: SSE stream
          content:
            text/event-stream:
              schema:
                type: string

  /api/v2/conversations/{id}/approve:
    post:
      summary: Approve current preview
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                message_id:
                  type: string
                  format: uuid
                  description: ID of approval message to approve
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Message'

  /api/v2/conversations/{id}/download:
    get:
      summary: Download filled PDF
      responses:
        '200':
          content:
            application/pdf:
              schema:
                type: string
                format: binary
        '404':
          description: No filled PDF available

components:
  schemas:
    Conversation:
      type: object
      properties:
        id:
          type: string
          format: uuid
        status:
          type: string
          enum: [active, completed, abandoned, error]
        title:
          type: string
        form_document_id:
          type: string
          format: uuid
        source_document_ids:
          type: array
          items:
            type: string
            format: uuid
        filled_pdf_ref:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    ConversationSummary:
      type: object
      properties:
        id:
          type: string
          format: uuid
        status:
          type: string
        title:
          type: string
        last_message_preview:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    Message:
      type: object
      properties:
        id:
          type: string
          format: uuid
        role:
          type: string
          enum: [user, agent, system]
        content:
          type: string
        thinking:
          type: string
        preview_ref:
          type: string
        approval_required:
          type: boolean
        approval_status:
          type: string
          enum: [pending, approved, rejected, edited]
        attachments:
          type: array
          items:
            $ref: '#/components/schemas/Attachment'
        metadata:
          type: object
        created_at:
          type: string
          format: date-time

    Attachment:
      type: object
      properties:
        id:
          type: string
          format: uuid
        filename:
          type: string
        content_type:
          type: string
        size_bytes:
          type: integer
        ref:
          type: string
        document_id:
          type: string
          format: uuid
```

### SSE Event Types

```typescript
// Server-Sent Events format
interface SSEEvent {
  event: string
  data: string  // JSON stringified
}

// Event types
type SSEEventType =
  | 'connected'      // Connection established
  | 'thinking'       // Agent is processing
  | 'message'        // New message from agent
  | 'preview'        // Preview image ready
  | 'approval'       // Approval requested
  | 'stage_change'   // Internal stage changed (optional)
  | 'error'          // Error occurred
  | 'complete'       // Conversation complete

// Example events
// event: connected
// data: {"conversation_id": "uuid"}

// event: thinking
// data: {"stage": "analyzing", "message": "Reading your documents..."}

// event: message
// data: {"id": "uuid", "role": "agent", "content": "I found 2 documents..."}

// event: preview
// data: {"message_id": "uuid", "preview_ref": "supabase://previews/..."}

// event: approval
// data: {"message_id": "uuid", "fields_to_approve": [...]}

// event: error
// data: {"code": "EXTRACTION_FAILED", "message": "Could not read PDF"}
```

### Error Handling

```typescript
// Error response format
interface ErrorResponse {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
    retry_after?: number  // seconds
  }
}

// Error codes
const ErrorCodes = {
  // Client errors (4xx)
  INVALID_FILE_TYPE: 'Only PDF and image files are supported',
  FILE_TOO_LARGE: 'File exceeds 50MB limit',
  TOO_MANY_FILES: 'Maximum 5 files per message',
  CONVERSATION_NOT_FOUND: 'Conversation not found',
  CONVERSATION_COMPLETED: 'Cannot modify completed conversation',
  RATE_LIMITED: 'Too many requests, please slow down',

  // Agent errors (5xx)
  AGENT_TIMEOUT: 'Agent took too long to respond',
  EXTRACTION_FAILED: 'Could not extract data from document',
  FILL_FAILED: 'Could not fill the form',
  LLM_ERROR: 'AI service temporarily unavailable',

  // Recovery actions
  RETRY_SUGGESTED: 'Please try again',
  UPLOAD_DIFFERENT: 'Try uploading a different document',
  CONTACT_SUPPORT: 'Contact support if issue persists',
}

// Automatic recovery
class AgentErrorHandler {
  async handleError(error: Error, context: AgentContext): Promise<AgentResponse> {
    // 1. Log error with context
    logger.error('Agent error', { error, conversationId: context.conversationId })

    // 2. Determine if retryable
    if (this.isRetryable(error) && context.retryCount < 3) {
      await this.retry(context)
      return
    }

    // 3. Send user-friendly message
    return {
      role: 'agent',
      content: this.getUserMessage(error),
      metadata: {
        error_code: error.code,
        recovery_action: this.getRecoveryAction(error),
      }
    }
  }
}
```

### File Upload Flow

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│ Browser │      │   API   │      │Supabase │      │  Agent  │
└────┬────┘      └────┬────┘      └────┬────┘      └────┬────┘
     │                │                │                │
     │ POST /messages │                │                │
     │ (multipart)    │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ Store file     │                │
     │                │───────────────>│                │
     │                │                │                │
     │                │ file_ref       │                │
     │                │<───────────────│                │
     │                │                │                │
     │                │ Create message │                │
     │                │ (with attachment)               │
     │                │───────────────>│                │
     │                │                │                │
     │ 202 Accepted   │                │                │
     │ (message_id)   │                │                │
     │<───────────────│                │                │
     │                │                │                │
     │                │ Trigger agent  │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │ SSE: thinking  │                │                │
     │<═══════════════│                │                │
     │                │                │   Process...   │
     │                │                │<───────────────│
     │                │                │                │
     │ SSE: message   │                │                │
     │<═══════════════│                │                │
     │                │                │                │
```

### Rate Limiting

```python
# Rate limit configuration
RATE_LIMITS = {
    'messages': {
        'window': 60,       # 1 minute
        'max_requests': 30,  # 30 messages per minute
    },
    'uploads': {
        'window': 3600,     # 1 hour
        'max_requests': 50,  # 50 uploads per hour
    },
    'conversations': {
        'window': 86400,    # 1 day
        'max_requests': 100, # 100 conversations per day
    },
}

# Redis-based rate limiter
async def check_rate_limit(user_id: str, action: str) -> bool:
    key = f"rate:{action}:{user_id}"
    config = RATE_LIMITS[action]

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, config['window'])

    return current <= config['max_requests']
```

---

## Appendix: Current vs New Architecture

```
CURRENT:
┌──────────┐    ┌──────────┐    ┌──────────┐
│  Mode    │ → │ Pipeline │ → │  Output  │
│ Selection│    │  Stages  │    │          │
└──────────┘    └──────────┘    └──────────┘
     ↑               ↑               ↑
     └───────────────┴───────────────┘
              User sees all of this

NEW:
┌──────────────────────────────────────────┐
│              Chat Interface              │
│  ┌────────────────────────────────────┐  │
│  │          Agent (LLM)               │  │
│  │  ┌─────────────────────────────┐   │  │
│  │  │   Pipeline (hidden)         │   │  │
│  │  │   INGEST→STRUCT→...→FILL    │   │  │
│  │  └─────────────────────────────┘   │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
              User sees only chat
```

---

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
│                                                             │
│   1. USER UPLOADS          2. AGENT AUTO-FILLS (SILENT)     │
│   ┌──────────┐             ┌──────────────────────┐         │
│   │ form.pdf │ ──────────► │ Fill ALL fields      │         │
│   │ source   │             │ - From source docs   │         │
│   └──────────┘             │ - From user profile  │         │
│                            │ - Smart defaults     │         │
│                            │ - Leave unknown blank│         │
│                            └──────────┬───────────┘         │
│                                       │                     │
│                                       ▼                     │
│   3. SHOW RESULT           4. USER ADJUSTS (IF NEEDED)      │
│   ┌──────────────────┐     ┌──────────────────────┐         │
│   │ "Filled 45       │     │ • Inline edit        │         │
│   │  fields"         │     │ • Chat commands      │         │
│   │                  │     │ • Or just download   │         │
│   │ [Preview]        │     │                      │         │
│   └──────────────────┘     └──────────────────────┘         │
│                                                             │
│   ────────────────────────────────────────────────────────  │
│   ZERO QUESTIONS ASKED until user initiates edit            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### System Architecture

#### Components, Tools, and Artifacts

**Components (Services + UI):**

Backend Services:
| Service | Internal Methods |
|---------|------------------|
| **Document Validator** | `validate()`, `check_quality()`, `check_content()` |
| Template Service | `search_by_embedding()`, `get_rules()`, `save_template()` |
| Bbox Service | `detect()`, `get_cached()`, `store()` |
| Document Service | `upload()`, `get()`, `delete()` |
| Extraction Service | `extract_from_source()`, `map_to_bboxes()` |
| Profile Service | `get_user_profile()`, `update()` |
| Learning Service | `save_correction()`, `get_corrections()` |

---

### Document Validator Service

**Purpose:** Gatekeeper that validates documents after upload before processing.

**Flow:**
```
User uploads ──► Document Validator ──► Processing
                      │
                      │ FAIL
                      ▼
                Reject with reason
```

**Validation Checks (LLM-driven):**

| Category | Checks |
|----------|--------|
| **Quality** | Image clarity, resolution, readability, file corruption |
| **Content** | Is it a form? Has fillable fields? Expected document type? |
| **Format** | Supported file type (PDF, PNG, JPG, TIFF) |

**Validation Results:**

| Result | Action |
|--------|--------|
| **Pass** | Continue to processing |
| **Fail** | Reject with reason (shown to user via `ask_user_input` or message) |

**Example Rejection Reasons:**
- "Image is too blurry to read"
- "This doesn't appear to be a fillable form"
- "File is corrupted or empty"
- "Unsupported file format"
- "Document has no detectable input fields"

| Visual Embedding Service | `generate_embedding()` |
| Vector DB | `search()`, `store()` |

Frontend UI:
| Component | Purpose |
|-----------|---------|
| Chat Panel | User-agent conversation |
| Preview Panel | Document preview with highlights |
| Inline Editor | Click-to-edit on fields |
| Field Info Panel | Show field details + font controls |
| Font Controls | Size, family, weight, color adjustment |
| Conversation Sidebar | History of past conversations |

---

### Font Control Feature

**Problem:** Text may be too long for bbox, causing overflow or clipping.

**Solution:** Auto-shrink by default + user font controls on field select.

**Behavior:**

```
┌─────────────────────────────────────────────────────────────┐
│  TEXT FITTING FLOW                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Agent fills text into bbox                              │
│          │                                                  │
│          ▼                                                  │
│  2. Check: Does text fit?                                   │
│          │                                                  │
│     YES  │  NO                                              │
│      │   │                                                  │
│      │   ▼                                                  │
│      │  3. Auto-shrink font until it fits                   │
│      │          │                                           │
│      │          ▼                                           │
│      └──► 4. Show in preview (with current font size)       │
│                  │                                          │
│                  ▼                                          │
│          5. User clicks field → Font controls appear        │
│                  │                                          │
│                  ▼                                          │
│          6. User can adjust: size, family, weight, color    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Font Controls UI (appears on field select):**

```
┌─────────────────────────────────────────────────────────────┐
│  Field: "Full Name"                                         │
│  Value: "Jonathan Alexander Smithington III"                │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Font Family:  [Arial          ▼]                           │
│  Font Size:    [10pt    ] [- ] [+]  (auto-shrunk from 12pt)│
│  Font Weight:  [Regular ▼]                                  │
│  Font Color:   [■ Black  ▼]                                 │
│                                                             │
│  [Reset to Default]                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Font Properties:**

| Property | Options | Default |
|----------|---------|---------|
| **Family** | Arial, Helvetica, Times New Roman, Courier | Arial |
| **Size** | 6pt - 72pt | 12pt (or auto-shrunk) |
| **Weight** | Light, Regular, Bold | Regular |
| **Color** | Black, Blue, Red, Custom hex | Black |

**Auto-Shrink Logic:**

```python
def fit_text_to_bbox(text: str, bbox: BBox, font: Font) -> Font:
    """Auto-shrink font until text fits in bbox."""
    current_size = font.size
    min_size = 6  # Never go below 6pt

    while current_size >= min_size:
        text_width = calculate_text_width(text, font.family, current_size)
        if text_width <= bbox.width:
            return font.with_size(current_size)
        current_size -= 0.5

    # Still doesn't fit at min size - truncate with ellipsis
    return font.with_size(min_size), truncate_with_ellipsis(text, bbox)
```

**Overflow Indicator:**

| State | Visual |
|-------|--------|
| Text fits | Normal display |
| Auto-shrunk | Yellow badge: "Shrunk to 10pt" |
| Truncated | Red badge: "Text truncated" + tooltip showing full text |

---

### Agents vs Services (CRITICAL DISTINCTION)

| Layer | Purpose | Powered By |
|-------|---------|------------|
| **Agents** | Thinking, reasoning, decisions | LLM (LangGraph) |
| **Services** | Execution, data operations | Code (no LLM) |

**Agents (Reasoning Layer):**

| Agent | Reasoning Focus |
|-------|-----------------|
| **DocumentUnderstandingAgent** | "What is this document? Form or source? What type?" |
| **ValidationAgent** | "Is quality good enough? Is content valid?" |
| **ExtractionAgent** | "What values are in this source document?" |
| **MappingAgent** | "Which extracted value goes to which bbox?" |
| **FormFillingAgent** | Main orchestrator - handles full flow + user edits |

**Services (Execution Layer):**

| Service | Execution Focus |
|---------|-----------------|
| Document Service | Upload, store, retrieve files |
| Template Service | Store/retrieve templates, vector search |
| Bbox Service | PyMuPDF bbox detection, caching |
| Profile Service | CRUD user profiles |
| Learning Service | Store corrections |
| Visual Embedding Service | Generate embeddings |
| PDF Renderer Service | Write values into bboxes |

**Agent ↔ Service Interaction:**

```
┌─────────────────────────────────────────────────────────────┐
│  AGENT (Reasoning)          SERVICE (Execution)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ValidationAgent:           Document Service:               │
│  "Is this readable?"   ───► get_document()                 │
│       │                                                     │
│       ▼                                                     │
│  "Yes, it's a W-9"                                         │
│                                                             │
│  MappingAgent:              Template Service:               │
│  "Map SSN to field 3" ───► get_template_rules()            │
│       │                                                     │
│       ▼                                                     │
│  "Field 3 = bbox(50,100)"                                  │
│                                                             │
│  FormFillingAgent:          PDF Renderer Service:           │
│  "Fill all fields"    ───► render_pdf(values, bboxes)      │
│       │                                                     │
│       ▼                                                     │
│  "Done, return PDF"                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

**Tools (Agent's General-Use Actions):**

| Tool | Purpose |
|------|---------|
| `render_preview` | Generate preview image of current state |
| `render_pdf` | Generate final filled PDF |

Only these are exposed as Tools - everything else is handled internally by services.

**Artifacts (Outputs):**

| Artifact | Description |
|----------|-------------|
| `filled_pdf` | Final filled document |
| `preview_image` | Visual preview of filled form |
| `conversation_log` | Chat history |
| `ask_user_input` | Interactive prompt (template picker, confirmation, etc.) |

---

### Input Model

```
┌─────────────────────────────────────────────────────────────┐
│  CHAT-BASED INPUT                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Primary: Text input                                        │
│  • User types messages to communicate                       │
│  • "Fill my name as John"                                   │
│  • "Change address to 123 Main St"                          │
│  • "Looks good, download"                                   │
│                                                             │
│  Secondary: ask_user_input (Claude-style keyboard nav)      │
│  • Agent presents options when structured input needed      │
│  • ↑↓ to navigate, Enter to select, 1/2/3 for quick select │
│  • User can also type instead of selecting                  │
│                                                             │
│  File upload: Drag & drop or paste                          │
│  • Drop files into chat                                     │
│  • Paste images                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Template System

**Template Structure:**
```json
{
  "id": "template-uuid",
  "name": "W-9",

  "embedding": [0.123, 0.456, ...],

  "bboxes": [
    { "id": 1, "x": 50, "y": 100, "w": 200, "h": 20 },
    { "id": 2, "x": 50, "y": 150, "w": 200, "h": 20 }
  ],

  "rules": [
    "Field 1 is Name, required",
    "Field 2 is SSN, format XXX-XX-XXXX"
  ]
}
```

**Template Matching Flow:**
```
User uploads form.pdf
        │
        ▼
┌─────────────────┐
│ Generate visual │
│ embedding       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Vector DB - Similarity Search          │
└────────┬────────────────────────────────┘
         │
         ▼
   Match found? ──YES──► Use template (bboxes + rules)
         │
         NO
         │
         ▼
   Fresh analysis by Agent
```

**Learning Flywheel:**
```
Manual Templates (top forms)
        │
        ▼
  User fills form
        │
        ▼
  User corrects fields
        │
        ▼
  Corrections stored per form type
        │
        ▼
  Next user benefits from improved template
```

---

### Agent Behavior Decisions

| Scenario | Behavior |
|----------|----------|
| Low confidence extraction | Fill anyway, show confidence badge |
| Format mismatch (user input) | Auto-convert silently |
| Invalid user input | Fill silently, don't block |
| Session resume | Silent restore, no chatty greeting |
| Multiple possible forms | Show template options via `ask_user_input` |
| User pivots to new form | Keep extracted data, apply to new form |
| Optional fields | Smart defaults, summarize what was filled |
| LLM API failure | Auto-retry 3x silently, then surface error |
| Data conflict | LLM resolves semantically |
| Form only (no source) | Fill from profile → ask for profile if none |
| Large document (50+ pages) | Smart extraction, detect relevant pages |
| Dropdown fields | Auto-select best option |

---

### UX Decisions

| Element | Decision |
|---------|----------|
| Agent tone | Professional minimal ("Filled 45 fields.") |
| Thinking process | Always show |
| Field click | Inline edit + field info panel |
| Checkboxes | Click to toggle in preview |
| Validation errors | Inline on field (red border + tooltip) |
| Undo/redo | Full stack (Ctrl+Z) |
| Success CTA | Save + Download (both) |
| Mobile | Same experience (responsive) |
| Empty fields | Yellow highlight in preview |
| Edit response | Batch after pause ("Updated 5 fields.") |
| Bulk text paste | Parse and auto-fill matching fields |

---

### Data & Security Decisions

| Aspect | Decision |
|--------|----------|
| PII retention | User chooses their strategy |
| PDF storage | Opt-in, stored in bucket |
| Profile save | Auto-save, easy delete |
| Concurrency | Lock conversation (one session) |

---

### Technical Priority Stack

```
┌─────────────────────────────────────────────────────────────┐
│  PRIORITY 1: BBOX DETECTION (Must have, 95%+ accuracy)      │
│  • Find all input areas in the form                         │
│  • Method: AcroForm first → Vision LLM fallback             │
├─────────────────────────────────────────────────────────────┤
│  PRIORITY 2: FIELD LABELING (Nice to have, decoupled)       │
│  • Identify what each bbox is                               │
│  • Templates accelerate this                                │
│  • LLM can figure it out if no template                     │
├─────────────────────────────────────────────────────────────┤
│  PRIORITY 3: VALUE FILLING (LLM-driven)                     │
│  • Extract values from source docs                          │
│  • Map to detected bboxes                                   │
│  • LLM handles the semantic matching                        │
└─────────────────────────────────────────────────────────────┘
```

---

### Architecture Diagram

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                    ┌──────────────────┐                    │
│   User Upload ───► │ DOCUMENT         │ ───► Processing    │
│                    │ VALIDATOR        │                    │
│                    │ (Quality+Content)│                    │
│                    └────────┬─────────┘                    │
│                             │ FAIL                         │
│                             ▼                              │
│                       Reject + Reason                      │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Visual       │  │ Vector DB    │  │ Template     │     │
│  │ Embedding    │  │ (Search)     │  │ Storage      │     │
│  │ Service      │  │              │  │ (bbox+rules) │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Bbox         │  │ Document     │  │ Learning     │     │
│  │ Detector     │  │ Storage      │  │ Service      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                            │
│                         │                                  │
│                         ▼                                  │
│              ┌─────────────────────┐                       │
│              │    AGENT (LLM)      │ ← ALL LOGIC           │
│              │                     │                       │
│              │  Tools:             │                       │
│              │  • render_preview   │                       │
│              │  • render_pdf       │                       │
│              │                     │                       │
│              │  Artifacts:         │                       │
│              │  • filled_pdf       │                       │
│              │  • preview_image    │                       │
│              │  • conversation_log │                       │
│              │  • ask_user_input   │                       │
│              └─────────────────────┘                       │
│                         │                                  │
│                         ▼                                  │
│              ┌─────────────────────┐                       │
│              │    Chat UI          │                       │
│              │    (keyboard-first) │                       │
│              └─────────────────────┘                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Coding Architecture Rules

> **Goal:** All external services swappable without changing business logic.

### Architectural Patterns (MUST USE)

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Adapter Pattern** | All external services | Swap implementations via interface |
| **Repository Pattern** | Data access | Abstract DB/storage operations |
| **Ports & Adapters** | Core domain | Isolate business logic from infrastructure |
| **Dependency Injection** | All services | Constructor injection, no hardcoded dependencies |

### Swappable Services

| Service | Interface | Implementations |
|---------|-----------|-----------------|
| **Storage** | `StoragePort` | `SupabaseStorageAdapter`, `S3Adapter`, `GCSAdapter` |
| **LLM** | `LLMPort` | `OpenAIAdapter`, `AnthropicAdapter`, `LocalLLMAdapter` |
| **Vector DB** | `VectorDBPort` | `PgVectorAdapter`, `PineconeAdapter`, `QdrantAdapter` |
| **Cache** | `CachePort` | `RedisAdapter`, `MemoryCacheAdapter` |
| **Auth** | `AuthPort` | `SupabaseAuthAdapter`, `Auth0Adapter`, `ClerkAdapter` |
| **Embedding** | `EmbeddingPort` | `OpenAICLIPAdapter`, `VertexAdapter`, `LocalEmbeddingAdapter` |

### Code Structure

```
app/
├── domain/                    # Core business logic (NO external deps)
│   ├── models/                # Domain models (pure Python)
│   ├── services/              # Business logic
│   └── ports/                 # Interfaces (abstract classes)
│       ├── storage.py         # StoragePort
│       ├── llm.py             # LLMPort
│       ├── vector_db.py       # VectorDBPort
│       ├── cache.py           # CachePort
│       └── auth.py            # AuthPort
│
├── adapters/                  # Infrastructure implementations
│   ├── storage/
│   │   ├── supabase.py        # SupabaseStorageAdapter
│   │   ├── s3.py              # S3Adapter
│   │   └── gcs.py             # GCSAdapter
│   ├── llm/
│   │   ├── openai.py          # OpenAIAdapter
│   │   └── anthropic.py       # AnthropicAdapter
│   ├── vector_db/
│   │   ├── pgvector.py        # PgVectorAdapter
│   │   └── pinecone.py        # PineconeAdapter
│   └── ...
│
├── config.py                  # Load adapters from env vars
└── main.py                    # Wire up dependencies
```

### Port Interface Example

```python
# app/domain/ports/storage.py
from abc import ABC, abstractmethod

class StoragePort(ABC):
    @abstractmethod
    async def upload(self, file: bytes, path: str) -> str:
        """Upload file, return URL."""
        pass

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download file by path."""
        pass

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file by path."""
        pass
```

### Adapter Implementation Example

```python
# app/adapters/storage/supabase.py
from app.domain.ports.storage import StoragePort

class SupabaseStorageAdapter(StoragePort):
    def __init__(self, supabase_client):
        self.client = supabase_client

    async def upload(self, file: bytes, path: str) -> str:
        result = await self.client.storage.upload(path, file)
        return result.url

    async def download(self, path: str) -> bytes:
        return await self.client.storage.download(path)

    async def delete(self, path: str) -> None:
        await self.client.storage.remove(path)
```

### Dependency Injection Example

```python
# app/config.py
import os
from app.domain.ports.storage import StoragePort
from app.adapters.storage.supabase import SupabaseStorageAdapter
from app.adapters.storage.s3 import S3Adapter

def get_storage_adapter() -> StoragePort:
    storage_type = os.getenv("STORAGE_TYPE", "supabase")

    if storage_type == "supabase":
        return SupabaseStorageAdapter(get_supabase_client())
    elif storage_type == "s3":
        return S3Adapter(get_s3_client())
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
```

### Coding Rules

| Rule | Description |
|------|-------------|
| **No direct imports** | Services import ports, not adapters |
| **Constructor injection** | Pass dependencies via `__init__`, no global state |
| **Config via env** | `STORAGE_TYPE=s3`, `LLM_PROVIDER=anthropic`, etc. |
| **Test with mocks** | Unit tests use mock adapters, never real services |
| **One adapter per file** | Easy to find and swap |

### Swapping Storage Example

```bash
# Current: Supabase
STORAGE_TYPE=supabase

# Switch to S3 (no code change)
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
S3_BUCKET=my-bucket
```

### Frontend Swappable Services

```typescript
// lib/ports/storage.ts
export interface StoragePort {
  upload(file: File): Promise<string>
  download(url: string): Promise<Blob>
  delete(url: string): Promise<void>
}

// lib/adapters/supabase-storage.ts
export class SupabaseStorageAdapter implements StoragePort {
  // implementation
}

// lib/config.ts
export function getStorageAdapter(): StoragePort {
  const type = process.env.NEXT_PUBLIC_STORAGE_TYPE
  if (type === 'supabase') return new SupabaseStorageAdapter()
  if (type === 's3') return new S3Adapter()
  throw new Error(`Unknown storage: ${type}`)
}
```

---

## Tech Stack (Lib-Heavy, Minimal Custom Code)

### Backend (Python/FastAPI)

| Category | Library | What it handles |
|----------|---------|-----------------|
| **API** | FastAPI | Routes, validation, OpenAPI |
| **Agent** | LangGraph | Stateful agent workflows, tools, state machine |
| **LLM** | langchain-openai, langchain-anthropic | LLM calls |
| **PDF Read** | PyMuPDF (fitz) | AcroForm extraction, bbox detection |
| **PDF Fill** | PyMuPDF (fitz) | Write values into bboxes |
| **PDF Preview** | PyMuPDF (fitz) | Render pages to PNG |
| **Embeddings** | Pluggable adapter | Visual embeddings (swap later) |
| **Vector Search** | pgvector + Supabase | Template similarity |
| **State** | Redis | Agent session state |
| **Streaming** | sse-starlette | SSE responses |
| **DB** | supabase-py | Postgres, Auth, Storage |
| **Validation** | Pydantic | Request/response models |

### Frontend (React/Vite or Next.js)

| Category | Library | What it handles |
|----------|---------|-----------------|
| **Framework** | Vite + React (or Next.js 14+) | Fast dev, SSR optional |
| **Chat Streaming** | AI SDK (`ai` package) | `useChat` hook for streaming, message state management |
| **Chat UI Components** | AI Elements (`ai-elements`) | Pre-built chat components (Conversation, Message, PromptInput, Response, Actions, Sources, Reasoning, Tool) |
| **UI Components** | shadcn/ui | Buttons, inputs, dialogs, etc. |
| **File Upload** | react-dropzone | Drag & drop |
| **Preview Display** | React Image components | Display PNG previews from backend |
| **State** | AI SDK built-in + React state | Minimal client state via `useChat` |
| **Styling** | Tailwind CSS | Utility classes |
| **Auth** | @supabase/auth-helpers-nextjs | Supabase auth integration |
| **API Client** | @supabase/supabase-js | DB, storage access |

#### AI Elements Components Used

| Component | Purpose |
|-----------|---------|
| `Conversation` | Main chat container with message list |
| `Message` | Individual message with role-based styling |
| `PromptInput` | User input with file attachment support |
| `Response` | Streaming AI response display |
| `Actions` | Message action buttons (copy, regenerate) |
| `Sources` | Citation/evidence display |
| `Reasoning` | Show agent thinking/reasoning |
| `Tool` | Tool call visualization |
| `CodeBlock` | Syntax-highlighted code display |

#### AI SDK Integration

```typescript
// useChat hook handles streaming and state
import { useChat } from 'ai/react';

const { messages, input, handleInputChange, handleSubmit, isLoading, status } = useChat({
  api: '/api/v2/conversations/{id}/chat',
  onFinish: (message) => { /* handle completion */ },
  onError: (error) => { /* handle error */ },
});

// Status values: 'submitted' | 'streaming' | 'ready' | 'error'
```

### Infrastructure

| Category | Service | What it handles |
|----------|---------|-----------------|
| **Database** | Supabase Postgres | All data |
| **Vector** | pgvector extension | Template embeddings |
| **Auth** | Supabase Auth | Users, sessions |
| **Storage** | Supabase Storage | PDFs, images |
| **Cache** | Redis (Upstash) | Agent state |

---

### What Libraries Handle (No Custom Code)

| Feature | Library |
|---------|---------|
| Chat streaming & state | AI SDK (`ai` package, `useChat` hook) |
| Chat UI components | AI Elements (Conversation, Message, PromptInput, etc.) |
| Agent state machine | LangGraph |
| PDF form detection | PyMuPDF |
| PDF form filling | PyMuPDF |
| PDF rendering | PyMuPDF |
| File drag & drop | react-dropzone |
| UI components | shadcn/ui |
| Auth flow | Supabase Auth |
| Real-time updates | SSE + AI SDK streaming |

### What We Build Custom (Minimal)

| Feature | Why Custom |
|---------|-----------|
| Template matching logic | Business logic for our flow |
| Agent tools | Connect LangGraph to our services |
| Learning/correction storage | Domain-specific schema |
| `ask_user_input` rendering | Match our UX spec |

---

## SaaS Model

### Features

| Feature | Description |
|---------|-------------|
| **Multi-tenancy** | Org/workspace isolation, team management, role-based access |
| **Billing** | Stripe integration, subscription management |
| **Usage Tracking** | Documents processed, API calls, storage used |
| **Plans** | Subscription tiers with limits |

### Subscription Tiers

| Tier | Limits | Features |
|------|--------|----------|
| **Free** | 10 docs/month, 100MB storage | Basic form filling |
| **Pro** | 100 docs/month, 1GB storage | Templates, batch processing, priority support |
| **Enterprise** | Unlimited | Custom templates, API access, SSO, dedicated support |

### Usage Tracking

| Metric | Tracked For |
|--------|-------------|
| Documents processed | Billing, limits |
| API calls | Rate limiting, billing |
| Storage used | Plan limits |
| LLM tokens | Cost tracking |

### Multi-tenancy Schema

```sql
-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Organization members
CREATE TABLE org_members (
    org_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES auth.users(id),
    role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (org_id, user_id)
);

-- Usage tracking
CREATE TABLE usage (
    id UUID PRIMARY KEY,
    org_id UUID REFERENCES organizations(id),
    metric TEXT NOT NULL,
    value INTEGER NOT NULL,
    period DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add org_id to conversations
ALTER TABLE conversations ADD COLUMN org_id UUID REFERENCES organizations(id);
```

---

## Development Workflow

### Commit Strategy: Feature Slices

Each commit is a **small vertical slice** that is deployable and testable.

```
┌─────────────────────────────────────────────────────────────┐
│  FEATURE SLICE EXAMPLE: "User can upload a document"        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Commit 1: API endpoint + storage                           │
│  ├── POST /api/documents                                    │
│  ├── Supabase storage integration                           │
│  └── Unit tests                                             │
│                                                             │
│  Commit 2: Document Validator                               │
│  ├── Validation service                                     │
│  ├── LLM integration for quality check                      │
│  └── Unit tests                                             │
│                                                             │
│  Commit 3: Frontend upload UI                               │
│  ├── react-dropzone component                               │
│  ├── API client                                             │
│  └── Component tests                                        │
│                                                             │
│  Commit 4: E2E test (critical path)                         │
│  └── Upload → Validate → Store flow                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Commit Rules

| Rule | Description |
|------|-------------|
| **Small** | Each commit does ONE thing |
| **Deployable** | Never break main branch |
| **Tested** | Unit tests with each commit |
| **Documented** | Clear commit message |

### Testing Strategy

| Test Type | When Required |
|-----------|---------------|
| **Unit tests** | Every commit |
| **Integration tests** | Service boundaries |
| **E2E tests** | Critical paths only |

### Critical Paths for E2E

| Path | Flow |
|------|------|
| **Happy path** | Upload → Validate → Template match → Auto-fill → Download |
| **Edit flow** | Upload → Fill → User edits → Download |
| **Auth flow** | Sign up → Sign in → Access conversation |

### Development with Claude Code

```
┌─────────────────────────────────────────────────────────────┐
│  CLAUDE CODE WORKFLOW                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Plan feature slice                                      │
│     └── Break into small commits                            │
│                                                             │
│  2. For each commit:                                        │
│     ├── Write tests first (TDD)                             │
│     ├── Implement minimal code to pass                      │
│     ├── Run tests                                           │
│     ├── Commit with clear message                           │
│     └── Verify CI passes                                    │
│                                                             │
│  3. After critical path complete:                           │
│     └── Add E2E test                                        │
│                                                             │
│  4. Review & iterate                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Parallel Development with Agents

Use **main agent + sub-agents** to develop independent components in parallel.

```
┌─────────────────────────────────────────────────────────────┐
│  PARALLEL AGENT DEVELOPMENT                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    ┌─────────────┐                          │
│                    │ MAIN AGENT  │                          │
│                    │ (Planner)   │                          │
│                    └──────┬──────┘                          │
│                           │                                 │
│           ┌───────────────┼───────────────┐                 │
│           │               │               │                 │
│           ▼               ▼               ▼                 │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│    │ Sub-Agent  │  │ Sub-Agent  │  │ Sub-Agent  │          │
│    │ Backend    │  │ Frontend   │  │ Tests      │          │
│    │            │  │            │  │            │          │
│    │ • API      │  │ • UI       │  │ • Unit     │          │
│    │ • Services │  │ • Components│ │ • E2E      │          │
│    │ • DB       │  │ • Hooks    │  │ • Fixtures │          │
│    └────────────┘  └────────────┘  └────────────┘          │
│           │               │               │                 │
│           └───────────────┼───────────────┘                 │
│                           │                                 │
│                           ▼                                 │
│                    ┌─────────────┐                          │
│                    │ MAIN AGENT  │                          │
│                    │ (Integrate) │                          │
│                    └─────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Responsibility |
|-------|----------------|
| **Main Agent** | Plan, coordinate, integrate, review |
| **Backend Sub-Agent** | FastAPI routes, services, DB schema |
| **Frontend Sub-Agent** | Next.js pages, components, hooks |
| **Test Sub-Agent** | Unit tests, integration tests, E2E |
| **Infra Sub-Agent** | Docker, CI/CD, deployment configs |

### Parallel Development Rules

| Rule | Description |
|------|-------------|
| **Contract-first (ALWAYS)** | Main agent defines OpenAPI specs + TypeScript types BEFORE spawning sub-agents |
| **One agent per service** | Each service/component gets its own sub-agent |
| **Max 4-5 parallel agents** | More than 5 becomes hard to coordinate |
| **Independent slices** | Sub-agents work on non-overlapping code |
| **Main agent integrates** | Only main agent merges and resolves conflicts |
| **Sync points** | Sub-agents complete → main agent reviews → commit |

### Parallel Development Flow

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: MAIN AGENT DEFINES CONTRACTS                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main Agent:                                                │
│  ├── Define OpenAPI spec for all endpoints                  │
│  ├── Define Pydantic models (backend)                       │
│  ├── Define TypeScript types (frontend)                     │
│  ├── Define service interfaces                              │
│  └── Commit contracts to repo                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: SPAWN SUB-AGENTS (Max 4-5 parallel)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Each sub-agent gets:                                       │
│  ├── Contract/interface to implement                        │
│  ├── Clear scope (one service or component)                 │
│  ├── Test requirements                                      │
│  └── No dependencies on other sub-agents                    │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Agent 1  │ │ Agent 2  │ │ Agent 3  │ │ Agent 4  │       │
│  │ Document │ │ Template │ │ Bbox     │ │ Chat UI  │       │
│  │ Validator│ │ Service  │ │ Service  │ │Component │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: MAIN AGENT INTEGRATES                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Main Agent:                                                │
│  ├── Review each sub-agent's work                           │
│  ├── Run integration tests                                  │
│  ├── Resolve any conflicts                                  │
│  ├── Commit integrated code                                 │
│  └── Run E2E tests                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Service → Sub-Agent Mapping

**Backend Services (each = 1 sub-agent):**

| Service | Sub-Agent Scope |
|---------|-----------------|
| Document Validator | `app/services/validator/` + tests |
| Template Service | `app/services/template/` + tests |
| Bbox Service | `app/services/bbox/` + tests |
| Document Service | `app/services/document/` + tests |
| Extraction Service | `app/services/extraction/` + tests |
| Profile Service | `app/services/profile/` + tests |
| Learning Service | `app/services/learning/` + tests |
| Visual Embedding | `app/services/embedding/` + tests |

**Frontend Components (each = 1 sub-agent):**

| Component | Sub-Agent Scope |
|-----------|-----------------|
| Chat Panel | `components/chat/` + tests |
| Preview Panel | `components/preview/` + tests |
| Inline Editor | `components/editor/` + tests |
| Field Info Panel | `components/field-info/` + tests |
| Conversation Sidebar | `components/sidebar/` + tests |
| File Upload | `components/upload/` + tests |

### Example: Phase 1 Parallel Execution

```
Main Agent:
├── Define contracts:
│   ├── POST /api/documents (upload)
│   ├── POST /api/documents/{id}/validate
│   ├── POST /api/documents/{id}/detect-bboxes
│   ├── DocumentUploadRequest, DocumentResponse types
│   └── Commit contracts

Spawn 4 sub-agents in parallel:
├── Sub-Agent 1: Document Validator Service
├── Sub-Agent 2: Bbox Detection Service
├── Sub-Agent 3: Chat Panel + Upload Component
├── Sub-Agent 4: Preview Panel Component

Each sub-agent:
├── Implements their contract
├── Writes unit tests
├── Returns when done

Main Agent:
├── Review all 4
├── Integrate
├── Run E2E: Upload → Validate → Detect → Preview
├── Commit
```

### Example: Parallel Feature Development

```
Feature: "Template Matching"

Main Agent:
├── Define API contract (OpenAPI spec)
├── Define data models (Pydantic/TypeScript)
└── Spawn sub-agents:

    Sub-Agent 1 (Backend):
    ├── Template storage service
    ├── Embedding service adapter
    ├── Vector search integration
    └── Unit tests

    Sub-Agent 2 (Frontend):
    ├── Template picker component
    ├── ask_user_input for selection
    └── Component tests

    Sub-Agent 3 (Tests):
    ├── Integration tests
    └── E2E: upload → template match → fill

Main Agent:
├── Review all sub-agent work
├── Integrate and resolve any conflicts
├── Run full test suite
└── Commit as feature slice
```

### When to Use Parallel Agents

| Scenario | Parallel? | Reason |
|----------|-----------|--------|
| Backend + Frontend for same feature | ✅ Yes | Independent codebases |
| Two backend services | ✅ Yes | If no shared dependencies |
| Service + its tests | ✅ Yes | Tests can be written in parallel |
| Sequential DB migrations | ❌ No | Must be ordered |
| Tightly coupled components | ❌ No | Risk of conflicts |

### Commit Message Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:** feat, fix, test, refactor, docs, chore

**Examples:**
```
feat(upload): add document upload API endpoint
test(upload): add unit tests for upload validation
feat(ui): add drag-drop upload component
test(e2e): add upload-to-download critical path
```

---

### Dependencies

**Backend (`pyproject.toml`):**
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109"
uvicorn = "^0.27"
langgraph = "^0.0.40"
langchain = "^0.1"
langchain-openai = "^0.0.5"
langchain-anthropic = "^0.1"
pymupdf = "^1.23"
redis = "^5.0"
supabase = "^2.3"
python-multipart = "^0.0.6"
pydantic = "^2.5"
sse-starlette = "^1.8"
```

**Frontend (`package.json`):**
```json
{
  "dependencies": {
    "react": "^18.2",
    "react-dom": "^18.2",
    "ai": "^2.2",
    "ai-elements": "latest",
    "@supabase/supabase-js": "^2.39",
    "react-dropzone": "^14.2",
    "tailwindcss": "^3.4"
  },
  "devDependencies": {
    "vite": "^5.0",
    "@vitejs/plugin-react": "^4.2"
  }
}
```

**Installing AI Elements:**
```bash
# Install AI Elements components (shadcn-style)
npx ai-elements@latest add conversation message prompt-input response

# Or install all components
npx ai-elements@latest add all
```

---

## Quick Reference

### Core Principles (MUST FOLLOW)

| # | Principle | Description |
|---|-----------|-------------|
| 1 | **Auto-fill first** | Fill ALL fields without asking. User edits after. |
| 2 | **LLM = All logic** | No static rules. No if/else business logic. Agent decides everything. |
| 3 | **Templates = Data** | Visual embedding + bboxes + rules. LLM reads as context. |
| 4 | **Trust the user** | Don't block invalid input. User knows their intent. |
| 5 | **Minimal communication** | "Filled 45 fields." Not "I've analyzed your form and found..." |

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
| **Frontend** | React + Vite, AI SDK (`useChat`), AI Elements (Chat UI), shadcn/ui, react-dropzone |
| **Database** | Supabase (Postgres + pgvector + Auth + Storage) |

### First Slice to Build

```
1. Backend: FastAPI + Supabase + document upload endpoint
2. Frontend: Next.js + chat input + file drop
3. Agent: Minimal LangGraph that calls PyMuPDF
4. E2E: Upload PDF → Get filled PDF back

This proves the full pipeline works before adding intelligence.
```

### Development Rules

| Rule | Enforcement |
|------|-------------|
| Small commits | One thing per commit |
| Tests with each commit | Unit tests required |
| E2E for critical paths | Upload→Fill→Download, Edit flow, Auth flow |
| Parallel agents | Backend + Frontend + Tests can run in parallel |
| Main agent integrates | Only main agent commits to main branch |
