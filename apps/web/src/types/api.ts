/**
 * Type-safe API types matching the backend contracts.
 * These types are derived from the FastAPI backend models.
 */

// ============================================================================
// Common Types
// ============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  meta: Record<string, unknown> | null;
}

export interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    field?: string;
    trace_id?: string;
  };
}

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page: number;
}

export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  has_more: boolean;
}

// ============================================================================
// Document Types
// ============================================================================

export type DocumentType = 'source' | 'target';

// ============================================================================
// AcroForm Types
// ============================================================================

export interface AcroFormFieldInfo {
  field_name: string;
  field_type: string;
  value: string;
  readonly: boolean;
  bbox: BBox;
}

export interface PageDimensions {
  page: number;
  width: number;
  height: number;
}

export interface AcroFormFieldsResponse {
  has_acroform: boolean;
  page_dimensions: PageDimensions[];
  fields: AcroFormFieldInfo[];
  preview_scale: number;
}

export interface DocumentMeta {
  page_count: number;
  file_size: number;
  mime_type: string;
  filename: string;
  has_password: boolean;
}

export interface Document {
  id: string;
  ref: string;
  document_type: DocumentType;
  meta: DocumentMeta;
  created_at: string;
}

export interface DocumentResponse {
  document_id: string;
  document_ref: string;
  meta: DocumentMeta;
}

// ============================================================================
// Field Types
// ============================================================================

export type FieldType = 'text' | 'number' | 'date' | 'checkbox' | 'radio' | 'signature' | 'image' | 'unknown';

export interface Field {
  id: string;
  name: string;
  field_type: FieldType;
  value: string | null;
  confidence: number | null;
  bbox: BBox | null;
  document_id: string;
  page: number;
  is_required: boolean;
  is_editable: boolean;
}

export interface FieldAnswer {
  field_id: string;
  value: string;
}

export interface FieldEdit {
  field_id: string;
  value?: string | null;
  bbox?: BBox | null;
  render_params?: Record<string, string | number | boolean> | null;
}

export interface Mapping {
  id: string;
  source_field_id: string;
  target_field_id: string;
  confidence: number;
  is_confirmed: boolean;
}

// ============================================================================
// Evidence Types
// ============================================================================

export interface Evidence {
  id: string;
  field_id: string;
  source: string;
  bbox: BBox | null;
  confidence: number;
  text: string | null;
  document_id: string;
}

export interface EvidenceResponse {
  field_id: string;
  evidence: Evidence[];
}

// ============================================================================
// Job Types
// ============================================================================

export type JobMode = 'transfer' | 'scratch';
export type JobStatus = 'created' | 'running' | 'blocked' | 'awaiting_input' | 'done' | 'failed';
export type RunMode = 'step' | 'until_blocked' | 'until_done';

export type ActivityAction =
  | 'job_created'
  | 'job_started'
  | 'document_uploaded'
  | 'extraction_started'
  | 'extraction_completed'
  | 'mapping_created'
  | 'field_extracted'
  | 'question_asked'
  | 'answer_received'
  | 'field_edited'
  | 'rendering_started'
  | 'rendering_completed'
  | 'job_completed'
  | 'job_failed'
  | 'error_occurred'
  | 'retry_started';

export type IssueType =
  | 'low_confidence'
  | 'missing_value'
  | 'validation_error'
  | 'mapping_ambiguous'
  | 'format_mismatch'
  | 'layout_issue';

export type IssueSeverity = 'info' | 'warning' | 'high' | 'critical' | 'error';

export interface Activity {
  id: string;
  timestamp: string;
  action: ActivityAction;
  details: Record<string, unknown>;
  field_id: string | null;
}

export interface Issue {
  id: string;
  field_id: string;
  issue_type: IssueType;
  message: string;
  severity: IssueSeverity;
  suggested_action: string | null;
}

export interface Extraction {
  id: string;
  field_id: string;
  value: string;
  confidence: number;
  evidence_ids: string[];
}

export interface CostBreakdown {
  llm_cost_usd: number;
  ocr_cost_usd: number;
  storage_cost_usd: number;
}

export interface CostSummary {
  llm_tokens_input: number;
  llm_tokens_output: number;
  llm_calls: number;
  ocr_pages_processed: number;
  ocr_regions_processed: number;
  storage_bytes_uploaded: number;
  storage_bytes_downloaded: number;
  estimated_cost_usd: number;
  breakdown: CostBreakdown;
  model_name: string;
}

export interface JobCreate {
  mode: JobMode;
  source_document_id?: string | null;
  target_document_id: string;
  rules?: Record<string, unknown> | null;
  thresholds?: Record<string, number> | null;
}

export interface JobContext {
  id: string;
  mode: JobMode;
  status: JobStatus;
  source_document: Document | null;
  target_document: Document;
  fields: Field[];
  mappings: Mapping[];
  extractions: Extraction[];
  evidence: Evidence[];
  issues: Issue[];
  activities: Activity[];
  created_at: string;
  updated_at: string;
  progress: number;
  current_step: string | null;
  current_stage: string | null;
  next_actions: string[];
  iteration_count: number;
  cost: CostSummary;
}

export interface JobResponse {
  job_id: string;
}

export interface RunRequest {
  run_mode: RunMode;
  max_steps?: number | null;
}

export interface RunResponse {
  status: JobStatus;
  job_context: JobContext;
  next_actions: string[];
}

export interface ConfidenceSummary {
  total_fields: number;
  high_confidence: number;
  medium_confidence: number;
  low_confidence: number;
  no_value: number;
  average_confidence: number;
}

export interface PagePreview {
  page: number;
  document_id: string;
  url: string;
  annotations: BBox[];
}

export interface ReviewResponse {
  issues: Issue[];
  previews: PagePreview[];
  fields: Field[];
  confidence_summary: ConfidenceSummary;
}

// ============================================================================
// Task Types (Async Processing)
// ============================================================================

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface RunAsyncRequest {
  run_mode: string;
  max_steps?: number | null;
}

export interface RunAsyncResponse {
  job_id: string;
  task_id: string;
  status: string;
  message: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatus;
  progress: number;
  job_id: string | null;
  stage: string | null;
  message: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
}

// ============================================================================
// Health Types
// ============================================================================

export interface ComponentHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency_ms: number | null;
  message: string | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  timestamp: string;
}

export interface ReadinessResponse extends HealthResponse {
  components: ComponentHealth[];
}

// ============================================================================
// Cost Detail Types
// ============================================================================

export interface CostDetailedBreakdown {
  llm_tokens_input: number;
  llm_tokens_output: number;
  llm_calls: number;
  ocr_pages_processed: number;
  ocr_regions_processed: number;
  storage_bytes_uploaded: number;
  storage_bytes_downloaded: number;
  estimated_cost_usd: number;
  breakdown: Record<string, number>;
  model_name: string;
  formatted_cost: string;
  formatted_storage: Record<string, string>;
}

// ============================================================================
// Fill Service Types
// ============================================================================

export interface FillValueRequest {
  field_id: string;
  value: string;
  x?: number | null;
  y?: number | null;
  width?: number | null;
  height?: number | null;
  page?: number | null;
}

export interface RenderParamsRequest {
  font_name?: string;
  font_size?: number;
  font_color?: [number, number, number];
  alignment?: 'left' | 'center' | 'right';
  line_height?: number;
  word_wrap?: boolean;
  overflow_handling?: 'truncate' | 'shrink' | 'error';
}

export interface FillServiceRequest {
  target_document_ref: string;
  fields: FillValueRequest[];
  method?: 'auto' | 'acroform' | 'overlay';
  render_params?: RenderParamsRequest | null;
  field_params?: Record<string, RenderParamsRequest> | null;
}

export interface FillIssue {
  field_id: string;
  issue_type: string;
  severity: string;
  message: string;
}

export interface FieldResult {
  field_id: string;
  success: boolean;
  value_written: string | null;
  issues: FillIssue[];
}

export interface FillServiceResponse {
  filled_document_ref: string | null;
  method_used: string;
  filled_count: number;
  failed_count: number;
  field_results: FieldResult[];
  errors: string[];
}
