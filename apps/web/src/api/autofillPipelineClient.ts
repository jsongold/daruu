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
