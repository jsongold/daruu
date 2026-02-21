# PRD: Agent-Driven Chat UI — Data Models

> **Source:** Split from [agent-chat-ui.md](../agent-chat-ui.md). See [README](README.md) for the full index.

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
