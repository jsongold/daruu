/**
 * Type-safe API client for field editing endpoints.
 * Provides functions for editing fields with undo/redo support.
 */

import { apiBaseUrl, ApiError } from './client';

// ============================================================================
// Types
// ============================================================================

/** Source of the edit (chat command or inline click) */
export type EditSource = 'chat' | 'inline';

/** A single field edit request */
export interface FieldEdit {
  /** Field ID to edit */
  field_id: string;
  /** New value for the field */
  value: string;
  /** Source of the edit */
  source: EditSource;
}

/** Response from a field update */
export interface EditResponse {
  /** Whether the edit was successful */
  success: boolean;
  /** Field ID that was edited */
  field_id: string;
  /** Previous value (null if field was empty) */
  old_value: string | null;
  /** New value after edit */
  new_value: string;
  /** Human-readable confirmation message */
  message: string;
}

/** Response from undo/redo operations */
export interface UndoRedoResponse {
  /** Which action was performed */
  action: 'undo' | 'redo';
  /** Edits that were reverted/reapplied */
  edits_reverted: FieldEdit[];
  /** Whether more undos are available */
  can_undo: boolean;
  /** Whether more redos are available */
  can_redo: boolean;
}

/** Edit history state */
export interface EditHistoryState {
  /** Whether undo is available */
  can_undo: boolean;
  /** Whether redo is available */
  can_redo: boolean;
  /** Number of edits in undo stack */
  undo_count: number;
  /** Number of edits in redo stack */
  redo_count: number;
}

/** Field data with value */
export interface FieldData {
  /** Field ID */
  field_id: string;
  /** Field label/name */
  label: string;
  /** Current value */
  value: string;
  /** Field type */
  type: 'text' | 'checkbox' | 'date' | 'number';
  /** Bounding box on the form (normalized coordinates) */
  bbox?: {
    x: number;
    y: number;
    width: number;
    height: number;
    page: number;
  } | null;
  /** Whether field is required */
  required?: boolean;
  /** Validation status */
  validation_status?: 'valid' | 'invalid' | 'warning' | null;
  /** Validation message */
  validation_message?: string | null;
}

/** Response from getting fields */
export interface FieldsResponse {
  /** All fields with their current values */
  fields: FieldData[];
  /** Edit history state */
  history: EditHistoryState;
}

/** API Response wrapper */
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// ============================================================================
// Configuration
// ============================================================================

const API_PREFIX = '/api/v2';

// ============================================================================
// HTTP Client Helper
// ============================================================================

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

  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T;
  }

  return response.json();
}

// ============================================================================
// Edit API Functions
// ============================================================================

/**
 * Update a single field value.
 * @param conversationId - The conversation ID
 * @param fieldId - The field ID to update
 * @param value - The new value
 * @param source - Source of the edit (default: 'inline')
 * @returns Edit response with old/new values
 */
export async function updateField(
  conversationId: string,
  fieldId: string,
  value: string,
  source: EditSource = 'inline'
): Promise<EditResponse> {
  const response = await request<ApiResponse<EditResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/fields/${encodeURIComponent(fieldId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ value, source }),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to update field',
      'EDIT_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Update multiple fields at once.
 * @param conversationId - The conversation ID
 * @param edits - Array of field edits
 * @returns Array of edit responses
 */
export async function batchUpdateFields(
  conversationId: string,
  edits: FieldEdit[]
): Promise<EditResponse[]> {
  const response = await request<ApiResponse<EditResponse[]>>(
    `${API_PREFIX}/conversations/${conversationId}/fields/batch`,
    {
      method: 'PATCH',
      body: JSON.stringify({ edits }),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to batch update fields',
      'BATCH_EDIT_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Undo the last edit(s).
 * @param conversationId - The conversation ID
 * @returns Undo response with reverted edits
 */
export async function undo(conversationId: string): Promise<UndoRedoResponse> {
  const response = await request<ApiResponse<UndoRedoResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/undo`,
    {
      method: 'POST',
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to undo',
      'UNDO_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Redo the last undone edit(s).
 * @param conversationId - The conversation ID
 * @returns Redo response with reapplied edits
 */
export async function redo(conversationId: string): Promise<UndoRedoResponse> {
  const response = await request<ApiResponse<UndoRedoResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/redo`,
    {
      method: 'POST',
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to redo',
      'REDO_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Get all fields with their current values.
 * @param conversationId - The conversation ID
 * @returns Fields with values and edit history state
 */
export async function getFields(conversationId: string): Promise<FieldsResponse> {
  const response = await request<ApiResponse<FieldsResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/fields`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get fields',
      'GET_FIELDS_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Get edit history state.
 * @param conversationId - The conversation ID
 * @returns Edit history state with undo/redo availability
 */
export async function getEditHistory(conversationId: string): Promise<EditHistoryState> {
  const response = await request<ApiResponse<EditHistoryState>>(
    `${API_PREFIX}/conversations/${conversationId}/edit-history`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get edit history',
      'HISTORY_ERROR',
      400
    );
  }

  return response.data;
}

// ============================================================================
// Utility Types for Local State
// ============================================================================

/** Local edit entry for history tracking */
export interface LocalEditEntry {
  /** Unique edit ID */
  id: string;
  /** Field ID */
  field_id: string;
  /** Value before edit */
  old_value: string;
  /** Value after edit */
  new_value: string;
  /** Timestamp of edit */
  timestamp: number;
  /** Source of edit */
  source: EditSource;
}

/** Local edit history for client-side tracking */
export interface LocalEditHistory {
  /** Undo stack */
  undoStack: LocalEditEntry[];
  /** Redo stack */
  redoStack: LocalEditEntry[];
}

/**
 * Create an empty local edit history.
 */
export function createEmptyHistory(): LocalEditHistory {
  return {
    undoStack: [],
    redoStack: [],
  };
}

/**
 * Generate a unique edit ID.
 */
export function generateEditId(): string {
  return `edit_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}
