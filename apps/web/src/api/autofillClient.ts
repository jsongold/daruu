/**
 * Type-safe API client for Vision Autofill endpoints.
 * Provides functions for AI-powered form field filling.
 */

import { apiBaseUrl, ApiError } from './client';

// ============================================================================
// Types
// ============================================================================

/** Field information for autofill request */
export interface AutofillFieldInfo {
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

/** Request for vision autofill */
export interface VisionAutofillRequest {
  /** Target document ID to fill */
  document_id: string;
  /** Conversation ID with data sources */
  conversation_id: string;
  /** Fields to fill with their definitions */
  fields: AutofillFieldInfo[];
  /** Optional rules for field filling */
  rules?: string[];
  /** Optional system prompt override for LLM */
  system_prompt?: string;
}

/** A field that was successfully filled */
export interface FilledField {
  /** Field identifier */
  field_id: string;
  /** Extracted value */
  value: string;
  /** Confidence score (0-1) */
  confidence: number;
  /** Data source that provided the value */
  source?: string | null;
}

/** Response from vision autofill */
export interface VisionAutofillResponse {
  /** Whether autofill succeeded */
  success: boolean;
  /** Fields that were filled with values */
  filled_fields: FilledField[];
  /** Field IDs that could not be filled */
  unfilled_fields: string[];
  /** Warnings about data quality or ambiguity */
  warnings: string[];
  /** Processing time in milliseconds */
  processing_time_ms: number;
  /** Error message if success=False */
  error?: string | null;
}

/** Summary of a data source extraction */
export interface ExtractionSummary {
  source_name: string;
  source_type: string;
  field_count: number;
}

/** Response from prompt preview */
export interface PromptPreviewResponse {
  /** System prompt that would be sent to LLM */
  system_prompt: string;
  /** User prompt that would be sent to LLM */
  user_prompt: string;
  /** Number of data sources found */
  data_source_count: number;
  /** Summary of each extraction */
  extractions_summary: ExtractionSummary[];
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
// Vision Autofill API
// ============================================================================

/**
 * Auto-fill form fields using AI vision.
 *
 * This function:
 * 1. Retrieves all data sources linked to the conversation
 * 2. Extracts text and structured data from each source
 * 3. Uses AI to match extracted data to form fields
 * 4. Returns filled values with confidence scores
 *
 * @param req - Autofill request with document ID, conversation ID, and fields
 * @returns Autofill response with filled fields and metadata
 */
export async function visionAutofill(
  req: VisionAutofillRequest
): Promise<VisionAutofillResponse> {
  const response = await request<ApiResponse<VisionAutofillResponse>>(
    `${API_PREFIX}/vision-autofill`,
    {
      method: 'POST',
      body: JSON.stringify(req),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Autofill failed',
      'AUTOFILL_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Preview the autofill prompt without calling the LLM.
 *
 * @param req - Same request body as autofill
 * @returns The system and user prompts that would be sent to the LLM
 */
export async function previewPrompt(
  req: VisionAutofillRequest
): Promise<PromptPreviewResponse> {
  const response = await request<ApiResponse<PromptPreviewResponse>>(
    `${API_PREFIX}/vision-autofill/preview-prompt`,
    {
      method: 'POST',
      body: JSON.stringify(req),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Preview prompt failed',
      'PREVIEW_PROMPT_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Auto-fill form fields with simplified parameters.
 *
 * Convenience wrapper that builds the request from common parameters.
 *
 * @param documentId - Target document ID
 * @param conversationId - Conversation ID with data sources
 * @param fields - Array of fields to fill
 * @param rules - Optional rules for field filling
 * @param systemPrompt - Optional system prompt override
 * @returns Autofill response with filled fields
 */
export async function autofillWithVision(
  documentId: string,
  conversationId: string,
  fields: Array<{
    field_id: string;
    label: string;
    type?: string;
    bbox?: { x: number; y: number; width: number; height: number; page: number } | null;
  }>,
  rules?: string[],
  systemPrompt?: string
): Promise<VisionAutofillResponse> {
  const req: VisionAutofillRequest = {
    document_id: documentId,
    conversation_id: conversationId,
    fields: fields.map(f => ({
      field_id: f.field_id,
      label: f.label,
      type: f.type || 'text',
      ...(f.bbox && {
        x: f.bbox.x,
        y: f.bbox.y,
        width: f.bbox.width,
        height: f.bbox.height,
        page: f.bbox.page,
      }),
    })),
    rules,
    ...(systemPrompt && { system_prompt: systemPrompt }),
  };

  return visionAutofill(req);
}

