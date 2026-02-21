/**
 * Type-safe API client for Prompt Attempt endpoints.
 * Isolated from the production autofill client.
 */

import { apiBaseUrl, ApiError } from './client';
import type { VisionAutofillRequest, VisionAutofillResponse } from './autofillClient';

// ============================================================================
// Types
// ============================================================================

/** A single prompt attempt (full detail) */
export interface PromptAttempt {
  id: string;
  conversation_id: string;
  document_id: string;
  system_prompt: string;
  user_prompt: string;
  custom_rules: string[];
  raw_response: string;
  parsed_result: Record<string, unknown> | null;
  success: boolean;
  error: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/** Response for list of prompt attempts */
export interface PromptAttemptList {
  items: PromptAttempt[];
  total: number;
}

/** Response from running a prompt attempt */
export interface RunAttemptResponse {
  attempt_id: string;
  autofill: VisionAutofillResponse;
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
// Prompt Attempt API
// ============================================================================

/**
 * Run autofill and store the attempt.
 *
 * Calls POST /api/v1/prompt-attempts/run which runs the production
 * autofill service and persists the prompt/response as a tuning attempt.
 *
 * @param req - Autofill request
 * @returns The stored attempt ID and autofill result
 */
export async function runPromptAttempt(
  req: VisionAutofillRequest
): Promise<RunAttemptResponse> {
  const response = await request<ApiResponse<RunAttemptResponse>>(
    `${API_PREFIX}/prompt-attempts/run`,
    {
      method: 'POST',
      body: JSON.stringify(req),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Run prompt attempt failed',
      'RUN_ATTEMPT_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * List prompt attempts for a conversation.
 *
 * @param conversationId - Conversation ID
 * @param limit - Max results (default 50)
 * @param offset - Results to skip (default 0)
 * @returns Paginated list of prompt attempts
 */
export async function listPromptAttempts(
  conversationId: string,
  limit: number = 50,
  offset: number = 0
): Promise<PromptAttemptList> {
  const params = new URLSearchParams({
    conversation_id: conversationId,
    limit: String(limit),
    offset: String(offset),
  });

  const response = await request<ApiResponse<PromptAttemptList>>(
    `${API_PREFIX}/prompt-attempts?${params.toString()}`,
    { method: 'GET' }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to list prompt attempts',
      'LIST_ATTEMPTS_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Get a single prompt attempt by ID.
 *
 * @param attemptId - Prompt attempt ID
 * @returns Full prompt attempt detail
 */
export async function getPromptAttempt(
  attemptId: string
): Promise<PromptAttempt> {
  const response = await request<ApiResponse<PromptAttempt>>(
    `${API_PREFIX}/prompt-attempts/${attemptId}`,
    { method: 'GET' }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get prompt attempt',
      'GET_ATTEMPT_ERROR',
      400
    );
  }

  return response.data;
}
