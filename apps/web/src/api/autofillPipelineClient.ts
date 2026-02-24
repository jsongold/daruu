/**
 * Type-safe API client for the Autofill Pipeline endpoint.
 * Uses the To-Be architecture: FormContextBuilder -> FillPlanner -> FormRenderer.
 */

import { apiBaseUrl, ApiError } from './client';

// ============================================================================
// Types
// ============================================================================

/** Field information for autofill request */
export interface AutofillPipelineFieldInfo {
  /** Unique field identifier */
  field_id: string;
  /** Field label/name */
  label: string;
  /** Field type: text, date, checkbox, number */
  type?: string;
  /** Bbox X coordinate (PDF points) */
  x?: number | null;
  /** Bbox Y coordinate (PDF points) */
  y?: number | null;
  /** Bbox width (PDF points) */
  width?: number | null;
  /** Bbox height (PDF points) */
  height?: number | null;
  /** Page number */
  page?: number | null;
}

/** Autofill mode */
export type AutofillMode = 'quick' | 'detailed';

/** Request for autofill pipeline */
export interface AutofillPipelineRequest {
  /** Target document ID to fill */
  document_id: string;
  /** Conversation ID with data sources */
  conversation_id: string;
  /** Fields to fill with their definitions */
  fields: AutofillPipelineFieldInfo[];
  /** Optional rules for field filling */
  rules?: string[];
  /** Autofill mode: quick (one-shot) or detailed (interactive Q&A) */
  mode?: AutofillMode;
}

/** A field that was successfully filled */
export interface PipelineFilledField {
  /** Field identifier */
  field_id: string;
  /** Filled value */
  value: string;
  /** Confidence score (0-1) */
  confidence: number;
  /** Data source that provided the value */
  source?: string | null;
}

/** A single pipeline step execution log */
export interface PipelineStepLog {
  /** Step identifier: context_build, rule_analyze, fill_plan, render */
  step_name: string;
  /** Step outcome: success, error, skipped */
  status: string;
  /** Time for this step in ms */
  duration_ms: number;
  /** Human-readable 1-line summary */
  summary: string;
  /** Step-specific structured data for drill-down */
  details: Record<string, unknown>;
  /** Error message if status=error */
  error?: string | null;
}

/** Response from autofill pipeline */
export interface AutofillPipelineResponse {
  /** Whether autofill succeeded */
  success: boolean;
  /** Fields that were filled with values */
  filled_fields: PipelineFilledField[];
  /** Field IDs that could not be filled */
  unfilled_fields: string[];
  /** Field IDs explicitly skipped */
  skipped_fields: string[];
  /** Field IDs requiring user input */
  ask_user_fields: string[];
  /** Reference to the filled PDF */
  filled_document_ref?: string | null;
  /** Processing time in milliseconds */
  processing_time_ms: number;
  /** Error message if failed */
  error?: string | null;
  /** Per-step pipeline execution logs */
  step_logs?: PipelineStepLog[];
}

/** API response wrapper */
interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: string | null;
  meta: Record<string, unknown> | null;
}

// ============================================================================
// HTTP Client Helper
// ============================================================================

const API_PREFIX = '/api/v1';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${apiBaseUrl}${endpoint}`;

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      try {
        errorBody = await response.text();
      } catch {
        errorBody = null;
      }
    }
    throw ApiError.fromResponse(response.status, errorBody);
  }

  return response.json();
}

// ============================================================================
// Autofill Pipeline API
// ============================================================================

/**
 * Auto-fill form fields using the To-Be pipeline.
 *
 * Uses the new architecture:
 * FormContextBuilder -> FillPlanner -> FormRenderer
 *
 * @param req - Autofill request with document ID, conversation ID, and fields
 * @returns Autofill response with filled fields and metadata
 */
export async function autofillPipeline(
  req: AutofillPipelineRequest
): Promise<AutofillPipelineResponse> {
  const response = await request<ApiResponse<AutofillPipelineResponse>>(
    `${API_PREFIX}/autofill`,
    {
      method: 'POST',
      body: JSON.stringify(req),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Autofill pipeline failed',
      'AUTOFILL_PIPELINE_ERROR',
      400
    );
  }

  return response.data;
}

// ============================================================================
// Detailed Mode: Turn Endpoint Types
// ============================================================================

/** A question option */
export interface QuestionOption {
  id: string;
  label: string;
}

/** A single conversation turn */
export interface ConversationTurn {
  role: 'assistant' | 'user';
  type: 'question' | 'answer' | 'fill_plan';
  question?: string | null;
  question_type?: 'single_choice' | 'multiple_choice' | 'free_text' | 'confirm' | null;
  options?: QuestionOption[];
  placeholder?: string | null;
  context?: string | null;
  selected_option_ids?: string[];
  free_text?: string | null;
}

/** Request for a single turn in detailed autofill mode */
export interface AutofillTurnRequest {
  document_id: string;
  conversation_id: string;
  fields: AutofillPipelineFieldInfo[];
  rules?: string[];
  conversation: ConversationTurn[];
  just_fill?: boolean;
}

/** Response from a single turn in detailed autofill mode */
export interface AutofillTurnResponse {
  type: 'question' | 'fill_plan';
  question?: string | null;
  question_type?: string | null;
  options?: QuestionOption[];
  context?: string | null;
  filled_fields?: PipelineFilledField[];
  unfilled_fields?: string[];
  skipped_fields?: string[];
  filled_document_ref?: string | null;
  processing_time_ms?: number;
  step_logs?: PipelineStepLog[];
}

/**
 * Execute a single turn in detailed autofill mode.
 *
 * Returns either a question (needs user answer) or a fill plan (done).
 */
export async function autofillTurn(
  req: AutofillTurnRequest
): Promise<AutofillTurnResponse> {
  const response = await request<ApiResponse<AutofillTurnResponse>>(
    `${API_PREFIX}/autofill/turn`,
    {
      method: 'POST',
      body: JSON.stringify(req),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Autofill turn failed',
      'AUTOFILL_TURN_ERROR',
      400
    );
  }

  return response.data;
}
