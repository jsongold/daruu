/**
 * Auto-generated TypeScript types from OpenAPI specification.
 * DO NOT EDIT MANUALLY - regenerate using scripts/generate_typescript.py
 *
 * Generated from: Daru PDF API
 * Version: 0.1.0
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

/** An activity record in the job timeline */
export interface Activity {
  /** Unique activity ID */
  id: string;
  /** Job ID this activity belongs to */
  job_id?: string;
  /** When the activity occurred */
  timestamp: string;
  /** Type of action */
  action:
    | "job_created"
    | "job_started"
    | "job_completed"
    | "job_failed"
    | "job_blocked"
    | "document_uploaded"
    | "document_processed"
    | "field_extracted"
    | "field_mapped"
    | "field_edited"
    | "field_confirmed"
    | "value_applied"
    | "question_asked"
    | "answer_provided"
    | "issue_detected"
    | "issue_resolved"
    | "review_started"
    | "output_generated";
  /** Actor who performed the action */
  actor?: "system" | "user" | "llm" | "ocr";
  /** Additional details */
  details?: Record<string, unknown>;
  /** Related field ID if applicable */
  field_id?: string | null;
  /** Human-readable message */
  message?: string;
}

/** Authentication response */
export interface AuthResponse {
  success: true;
  data: {
    token: string;
    expires_at: string;
  };
}

/** Bounding box coordinates on a page */
export interface BBox {
  /** Page number (1-indexed) */
  page: number;
  /** X coordinate (normalized 0-1 or pixels) */
  x: number;
  /** Y coordinate (normalized 0-1 or pixels) */
  y: number;
  /** Width of the bounding box */
  width: number;
  /** Height of the bounding box */
  height: number;
}

/** Summary of confidence scores across fields */
export interface ConfidenceSummary {
  /** Average confidence score */
  average: number;
  /** Minimum confidence score */
  min?: number;
  /** Maximum confidence score */
  max?: number;
  /** Number of fields with low confidence */
  low_confidence_count?: number;
  /** Total number of fields */
  total_fields: number;
}

/** A document uploaded to the system */
export interface Document {
  /** Unique identifier */
  id: string;
  /** Reference path or filename */
  ref: string;
  /** Document metadata */
  meta: DocumentMeta;
}

/** Response for getting a document by ID */
export interface DocumentGetResponse {
  success: true;
  data: Document;
}

/** Metadata about a document */
export interface DocumentMeta {
  /** Number of pages */
  page_count: number;
  /** File size in bytes */
  size_bytes: number;
  /** MIME type */
  mime_type: string;
  /** Upload timestamp */
  created_at: string;
  /** Original filename */
  filename?: string;
  /** File checksum */
  checksum?: string;
}

/** Response after successful document upload */
export interface DocumentUploadResponse {
  success: true;
  data: Document;
}

/** Standard error response format */
export interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    trace_id?: string;
  };
}

/** Evidence supporting a field extraction */
export interface Evidence {
  /** Unique evidence ID */
  id: string;
  /** Document this evidence is from */
  document_id: string;
  /** Source of evidence */
  source: "ocr" | "llm" | "form_field" | "annotation" | "manual";
  /** Bounding box location */
  bbox?: BBox | null;
  /** Extracted text */
  text?: string;
  /** Confidence score */
  confidence: number;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
  /** Creation timestamp */
  created_at?: string;
}

/** Extracted value for a field */
export interface Extraction {
  /** Unique extraction ID */
  id: string;
  /** Field ID this extraction is for */
  field_id: string;
  /** Extracted value */
  value: string | number | boolean | null;
  /** Confidence score */
  confidence: number;
  /** Evidence references */
  evidence_refs?: Array<{
    evidence_id: string;
    relevance?: number;
  }>;
  /** Extraction status */
  status?: "pending" | "extracted" | "confirmed" | "rejected";
  /** Extraction method */
  method?: "ocr" | "llm" | "rule" | "manual";
  /** Creation timestamp */
  created_at?: string;
}

/** A form field in a document */
export interface Field {
  /** Unique field ID */
  id: string;
  /** Field name/label */
  name: string;
  /** Type of field */
  type: "text" | "number" | "date" | "checkbox" | "signature" | "image";
  /** Current field value */
  value?: string | number | boolean | null;
  /** Confidence score */
  confidence?: number;
  /** Bounding box location */
  bbox?: BBox | null;
  /** Source of field value */
  source?: "extracted" | "manual" | "default";
  /** Document this field belongs to */
  document_id?: string;
  /** Field label text */
  label?: string;
  /** Whether field is required */
  required?: boolean;
}

/** An issue or problem with a field */
export interface Issue {
  /** Unique issue ID */
  id: string;
  /** Job this issue belongs to */
  job_id?: string;
  /** Field with the issue */
  field_id?: string;
  /** Type of issue */
  type:
    | "missing_value"
    | "low_confidence"
    | "format_error"
    | "validation_error"
    | "conflict"
    | "ambiguous_mapping"
    | "unreadable_content"
    | "password_protected"
    | "unsupported_format";
  /** Severity level */
  severity: "error" | "warning" | "info";
  /** Human-readable message */
  message: string;
  /** Issue status */
  status?: "open" | "resolved" | "ignored";
  /** Suggested resolution */
  suggestion?: string;
  /** Additional details */
  details?: Record<string, unknown>;
  /** Creation timestamp */
  created_at?: string;
  /** Resolution timestamp */
  resolved_at?: string;
}

/** Response for activity log endpoint */
export interface JobActivityResponse {
  success: true;
  data: {
    activities: Activity[];
  };
}

/** Request to submit answers */
export interface JobAnswersRequest {
  answers: Array<{
    field_id: string;
    value: string | number | boolean | null;
  }>;
}

/** Job configuration options */
export interface JobConfig {
  /** Confidence threshold for auto-accept */
  confidence_threshold?: number;
  /** Whether to auto-apply extractions */
  auto_apply?: boolean;
  /** Whether to require review */
  require_review?: boolean;
}

/** Full context of a job including all state */
export interface JobContext {
  /** Unique job ID */
  id: string;
  /** Current status */
  status: "pending" | "running" | "blocked" | "done" | "failed";
  /** Job mode */
  mode: "transfer" | "scratch";
  /** Source document ID (for transfer mode) */
  source_document_id?: string;
  /** Target document ID */
  target_document_id: string;
  /** Job configuration */
  config?: JobConfig;
  /** All fields */
  fields?: Field[];
  /** Field mappings */
  mappings?: Mapping[];
  /** Extracted values */
  extractions?: Extraction[];
  /** Current issues */
  issues?: Issue[];
  /** Activity timeline */
  activities?: Activity[];
  /** Confidence summary */
  confidence_summary?: ConfidenceSummary;
  /** Available next actions */
  next_actions?: NextAction[];
  /** Progress information */
  progress?: {
    current_step?: string;
    total_steps?: number;
    completed_steps?: number;
    percentage?: number;
  };
  /** Creation timestamp */
  created_at: string;
  /** Last update timestamp */
  updated_at: string;
  /** Completion timestamp */
  completed_at?: string;
  /** Error information if failed */
  error?: {
    code: string;
    message: string;
    trace_id?: string;
  };
}

/** Request to create a new job */
export interface JobCreateRequest {
  /** Job mode */
  mode: "transfer" | "scratch";
  /** Source document ID (required for transfer mode) */
  source_document_id?: string;
  /** Target document ID */
  target_document_id: string;
  /** Job configuration */
  config?: JobConfig;
}

/** Response after job creation */
export interface JobCreateResponse {
  success: true;
  data: {
    job_id: string;
  };
}

/** Request to submit edits */
export interface JobEditsRequest {
  edits: Array<{
    field_id: string;
    value?: string | number | boolean | null;
    bbox?: BBox;
    render_params?: Record<string, unknown>;
  }>;
}

/** Response for evidence endpoint */
export interface JobEvidenceResponse {
  success: true;
  data: {
    evidence: Evidence[];
  };
}

/** Export job data response */
export interface JobExportResponse {
  success: true;
  data: {
    job: JobContext;
    evidence?: Evidence[];
  };
}

/** Response for getting job by ID */
export interface JobGetResponse {
  success: true;
  data: JobContext;
}

/** Response for job review endpoint */
export interface JobReviewResponse {
  success: true;
  data: {
    issues: Issue[];
    fields: Field[];
    confidence_summary: ConfidenceSummary;
    previews?: Array<{
      page: number;
      url: string;
    }>;
  };
}

/** Request to run a job */
export interface JobRunRequest {
  /** Run mode */
  run_mode: "step" | "until_blocked" | "until_done";
  /** Maximum steps to execute */
  max_steps?: number;
}

/** Response after running a job */
export interface JobRunResponse {
  success: true;
  data: {
    status: "pending" | "running" | "blocked" | "done" | "failed";
    job_context: JobContext;
    next_actions?: NextAction[];
  };
}

/** Field mapping between source and target */
export interface Mapping {
  /** Unique mapping ID */
  id: string;
  /** Source field ID */
  source_field_id: string;
  /** Target field ID */
  target_field_id: string;
  /** Mapping confidence */
  confidence: number;
  /** Mapping status */
  status?: "pending" | "confirmed" | "rejected" | "applied";
  /** Transform function */
  transform?: string;
  /** Creation timestamp */
  created_at?: string;
  /** Update timestamp */
  updated_at?: string;
}

/** Next action for a job */
export interface NextAction {
  /** Action type */
  type: "provide_answer" | "review_field" | "confirm_mapping" | "resolve_issue";
  /** Related field ID */
  field_id?: string;
  /** Related issue ID */
  issue_id?: string;
  /** Question to ask */
  question?: string;
  /** Answer options */
  options?: string[];
}

/** Success response */
export interface SuccessResponse {
  success: true;
}

/** User information response */
export interface UserResponse {
  success: true;
  data: {
    id: string;
    email: string;
    name?: string;
  };
}

// API Response Wrappers

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    field?: string;
    trace_id?: string;
  };
}

// Request/Response type helpers

export type DocumentUploadRequest = FormData;

export type CreateJobRequest = JobCreateRequest;
export type CreateJobResponse = ApiResponse<{ job_id: string }>;

export type GetJobResponse = ApiResponse<JobContext>;
export type RunJobResponse = ApiResponse<JobRunResponse>;

// Field types
export type FieldType = "text" | "number" | "date" | "checkbox" | "signature" | "image";
export type FieldSource = "extracted" | "manual" | "default";

// Job types
export type JobStatus = "pending" | "running" | "blocked" | "done" | "failed";
export type JobMode = "transfer" | "scratch";
export type RunMode = "step" | "until_blocked" | "until_done";

// Issue types
export type IssueSeverity = "error" | "warning" | "info";
export type IssueType =
  | "missing_value"
  | "low_confidence"
  | "format_error"
  | "validation_error"
  | "conflict"
  | "ambiguous_mapping"
  | "unreadable_content"
  | "password_protected"
  | "unsupported_format";

// Activity types
export type ActivityAction =
  | "job_created"
  | "job_started"
  | "job_completed"
  | "job_failed"
  | "job_blocked"
  | "document_uploaded"
  | "document_processed"
  | "field_extracted"
  | "field_mapped"
  | "field_edited"
  | "field_confirmed"
  | "value_applied"
  | "question_asked"
  | "answer_provided"
  | "issue_detected"
  | "issue_resolved"
  | "review_started"
  | "output_generated";

export type ActivityActor = "system" | "user" | "llm" | "ocr";

// Evidence types
export type EvidenceSource = "ocr" | "llm" | "form_field" | "annotation" | "manual";

// Extraction types
export type ExtractionStatus = "pending" | "extracted" | "confirmed" | "rejected";
export type ExtractionMethod = "ocr" | "llm" | "rule" | "manual";

// Mapping types
export type MappingStatus = "pending" | "confirmed" | "rejected" | "applied";

// Next action types
export type NextActionType = "provide_answer" | "review_field" | "confirm_mapping" | "resolve_issue";

// ============================================
// Agent Chat UI Types (from PRD agent-chat-ui.md)
// ============================================

/** Conversation status */
export type ConversationStatus = "active" | "completed" | "abandoned" | "error";

/** Message role */
export type MessageRole = "user" | "agent" | "system";

/** Approval status */
export type ApprovalStatus = "pending" | "approved" | "rejected" | "edited";

/** Agent processing stage */
export type AgentStage =
  | "idle"
  | "analyzing"
  | "confirming"
  | "mapping"
  | "filling"
  | "reviewing"
  | "complete"
  | "error";

/** SSE event types */
export type SSEEventType =
  | "connected"
  | "thinking"
  | "message"
  | "preview"
  | "approval"
  | "stage_change"
  | "error"
  | "complete";

/** Chat error codes */
export type ChatErrorCode =
  | "INVALID_FILE_TYPE"
  | "FILE_TOO_LARGE"
  | "TOO_MANY_FILES"
  | "CONVERSATION_NOT_FOUND"
  | "CONVERSATION_COMPLETED"
  | "RATE_LIMITED"
  | "AGENT_TIMEOUT"
  | "EXTRACTION_FAILED"
  | "FILL_FAILED"
  | "LLM_ERROR";

/** An attachment on a message */
export interface Attachment {
  /** Unique attachment ID */
  id: string;
  /** Original filename */
  filename: string;
  /** MIME type */
  content_type: string;
  /** File size in bytes */
  size_bytes: number;
  /** Storage reference URL */
  ref: string;
  /** Linked document ID if processed */
  document_id?: string | null;
}

/** A message in a conversation */
export interface Message {
  /** Unique message ID */
  id: string;
  /** Message sender role */
  role: MessageRole;
  /** Message text content */
  content: string;
  /** Agent's internal reasoning (optional) */
  thinking?: string | null;
  /** Preview image URL */
  preview_ref?: string | null;
  /** Whether approval is needed */
  approval_required: boolean;
  /** Approval status if applicable */
  approval_status?: ApprovalStatus | null;
  /** Message attachments */
  attachments: Attachment[];
  /** Additional metadata */
  metadata: Record<string, unknown>;
  /** Creation timestamp */
  created_at: string;
}

/** A conversation with the agent */
export interface Conversation {
  /** Unique conversation ID */
  id: string;
  /** Current status */
  status: ConversationStatus;
  /** Conversation title */
  title?: string | null;
  /** Form document ID */
  form_document_id?: string | null;
  /** Source document IDs */
  source_document_ids: string[];
  /** Filled PDF storage reference */
  filled_pdf_ref?: string | null;
  /** Creation timestamp */
  created_at: string;
  /** Last update timestamp */
  updated_at: string;
}

/** Summary of a conversation for list views */
export interface ConversationSummary {
  /** Unique conversation ID */
  id: string;
  /** Current status */
  status: ConversationStatus;
  /** Conversation title */
  title?: string | null;
  /** Preview of last message */
  last_message_preview?: string | null;
  /** Creation timestamp */
  created_at: string;
  /** Last update timestamp */
  updated_at: string;
}

/** Conversation with recent messages */
export interface ConversationWithMessages {
  /** Conversation details */
  conversation: Conversation;
  /** Recent messages */
  messages: Message[];
}

/** Paginated list of conversations */
export interface ConversationListResponse {
  /** Conversation summaries */
  items: ConversationSummary[];
  /** Cursor for next page */
  next_cursor?: string | null;
}

/** Paginated list of messages */
export interface MessageListResponse {
  /** Messages */
  items: Message[];
  /** Whether more messages exist */
  has_more: boolean;
}

/** Request to create a new conversation */
export interface CreateConversationRequest {
  /** Optional title (auto-generated if not provided) */
  title?: string | null;
}

/** Request to send a message */
export interface SendMessageRequest {
  /** Message text content */
  content: string;
}

/** Request to approve a preview */
export interface ApprovePreviewRequest {
  /** ID of the approval message to approve */
  message_id: string;
}

// ============================================
// SSE Event Data Types
// ============================================

/** Data for 'connected' event */
export interface SSEConnectedData {
  conversation_id: string;
}

/** Data for 'thinking' event */
export interface SSEThinkingData {
  stage: AgentStage;
  message: string;
}

/** Data for 'message' event */
export interface SSEMessageData {
  id: string;
  role: MessageRole;
  content: string;
}

/** Data for 'preview' event */
export interface SSEPreviewData {
  message_id: string;
  preview_ref: string;
}

/** Data for 'approval' event */
export interface SSEApprovalData {
  message_id: string;
  fields_to_approve: string[];
}

/** Data for 'stage_change' event */
export interface SSEStageChangeData {
  previous_stage: AgentStage;
  new_stage: AgentStage;
}

/** Data for 'error' event */
export interface SSEErrorData {
  code: ChatErrorCode;
  message: string;
}

/** Generic SSE event */
export interface SSEEvent<T = unknown> {
  event: SSEEventType;
  data: T;
}

// ============================================
// Agent State Types
// ============================================

/** A document detected by the agent */
export interface DetectedDocument {
  /** Document ID */
  document_id: string;
  /** Original filename */
  filename: string;
  /** Detected type: form or source */
  document_type: "form" | "source";
  /** Detection confidence */
  confidence: number;
  /** Number of pages */
  page_count: number;
  /** Preview image URL */
  preview_ref?: string | null;
}

/** Current state of agent for a conversation */
export interface AgentState {
  /** Conversation ID */
  conversation_id: string;
  /** Current processing stage */
  current_stage: AgentStage;
  /** Documents detected */
  detected_documents: DetectedDocument[];
  /** Detected form fields */
  form_fields: Record<string, unknown>[];
  /** Extracted field values */
  extracted_values: Record<string, unknown>[];
  /** Questions for user */
  pending_questions: Record<string, unknown>[];
  /** Last error message */
  last_error?: string | null;
  /** Retry attempt count */
  retry_count: number;
  /** Last activity timestamp */
  last_activity: string;
}

// ============================================
// Chat Error Types
// ============================================

/** Chat error detail */
export interface ChatErrorDetail {
  code: ChatErrorCode;
  message: string;
  details?: Record<string, unknown> | null;
  retry_after?: number | null;
}

/** Chat error response */
export interface ChatErrorResponse {
  error: ChatErrorDetail;
}

// ============================================
// Template System Types (Phase 2)
// ============================================

/** A form template in the system */
export interface Template {
  /** Unique template ID */
  id: string;
  /** Template display name */
  name: string;
  /** Type of form (e.g., "W-2", "1099", "I-9") */
  form_type: string;
  /** Preview image URL (if available) */
  preview_url: string | null;
  /** Number of fields in the template */
  field_count: number;
}

/** A template match result from visual similarity matching */
export interface TemplateMatch {
  /** Matched template ID */
  template_id: string;
  /** Template display name */
  template_name: string;
  /** Similarity score (0-1) */
  similarity_score: number;
  /** Preview image URL (if available) */
  preview_url: string | null;
  /** Number of fields in the template */
  field_count: number;
}

/** User input type for ask_user_input pattern */
export type AskUserInputType =
  | 'template_selection'
  | 'field_confirmation'
  | 'value_clarification'
  | 'document_classification';

/** Metadata for template selection user input */
export interface TemplateSelectionMetadata {
  type: 'template_selection';
  matches: TemplateMatch[];
  document_id?: string;
  page_number?: number;
}

/** Generic ask_user_input metadata */
export type AskUserInputMetadata =
  | TemplateSelectionMetadata
  | { type: AskUserInputType; [key: string]: unknown };

// ============================================
// Data Source Types (for AI form filling)
// ============================================

/** Type of data source */
export type DataSourceType = 'pdf' | 'image' | 'text' | 'csv';

/** A data source for AI form filling */
export interface DataSource {
  /** Unique data source ID */
  id: string;
  /** Type of data source */
  type: DataSourceType;
  /** Display name (usually original filename) */
  name: string;
  /** Reference to documents table for files */
  document_id?: string | null;
  /** First 500 chars for preview */
  content_preview?: string | null;
  /** Cached AI extraction results */
  extracted_data?: Record<string, unknown> | null;
  /** File size in bytes */
  file_size_bytes?: number | null;
  /** MIME type */
  mime_type?: string | null;
  /** Creation timestamp */
  created_at: string;
}

/** Response for a single data source */
export interface DataSourceResponse {
  /** Unique data source ID */
  id: string;
  /** Type of data source */
  type: DataSourceType;
  /** Display name */
  name: string;
  /** Reference to documents table */
  document_id?: string | null;
  /** First 500 chars for preview */
  content_preview?: string | null;
  /** Cached extraction results */
  extracted_data?: Record<string, unknown> | null;
  /** File size in bytes */
  file_size_bytes?: number | null;
  /** MIME type */
  mime_type?: string | null;
  /** Creation timestamp */
  created_at: string;
}

/** Response for list of data sources */
export interface DataSourceListResponse {
  /** List of data sources */
  items: DataSourceResponse[];
  /** Total count */
  total: number;
}

/** Result of AI extraction from a data source */
export interface ExtractionResult {
  /** Data source ID */
  data_source_id: string;
  /** Extracted field name-value pairs */
  extracted_fields: Record<string, unknown>;
  /** Overall extraction confidence */
  confidence: number;
  /** Raw extracted text */
  raw_text?: string | null;
}
