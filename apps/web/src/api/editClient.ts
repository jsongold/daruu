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

/** Font style options for field rendering */
export interface FontStyle {
  /** Font size in points */
  fontSize?: number;
  /** Font family name */
  fontFamily?: 'Helvetica' | 'Times' | 'Courier';
  /** Font color as hex string (e.g., "#000000") */
  fontColor?: string;
  /** Text alignment */
  alignment?: 'left' | 'center' | 'right';
}

/** Default font style values */
export const DEFAULT_FONT_STYLE: Required<FontStyle> = {
  fontSize: 12,
  fontFamily: 'Helvetica',
  fontColor: '#000000',
  alignment: 'left',
};

/** Available font size presets */
export const FONT_SIZE_PRESETS = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32] as const;

/** Available font family options */
export const FONT_FAMILY_OPTIONS: Array<{ value: FontStyle['fontFamily']; label: string }> = [
  { value: 'Helvetica', label: 'Helvetica (Sans-serif)' },
  { value: 'Times', label: 'Times (Serif)' },
  { value: 'Courier', label: 'Courier (Monospace)' },
];

/** Common color presets */
export const FONT_COLOR_PRESETS = [
  { value: '#000000', label: 'Black' },
  { value: '#1f2937', label: 'Dark Gray' },
  { value: '#374151', label: 'Gray' },
  { value: '#1e40af', label: 'Blue' },
  { value: '#dc2626', label: 'Red' },
  { value: '#16a34a', label: 'Green' },
];

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
  /** Font style for this field */
  fontStyle?: FontStyle;
}

/** Response from getting fields */
export interface FieldsResponse {
  /** All fields with their current values */
  fields: FieldData[];
  /** Edit history state */
  history: EditHistoryState;
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
  // Backend returns EditResponse directly (not wrapped in ApiResponse)
  return request<EditResponse>(
    `${API_PREFIX}/conversations/${conversationId}/fields/${encodeURIComponent(fieldId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ value, source }),
    }
  );
}

/**
 * Update multiple fields at once.
 * @param conversationId - The conversation ID
 * @param edits - Array of field edits
 * @returns Batch edit response with individual results
 */
export async function batchUpdateFields(
  conversationId: string,
  edits: FieldEdit[]
): Promise<{ success: boolean; results: EditResponse[]; summary: string }> {
  // Backend returns BatchEditResponse directly (not wrapped in ApiResponse)
  return request<{ success: boolean; results: EditResponse[]; summary: string }>(
    `${API_PREFIX}/conversations/${conversationId}/fields/batch`,
    {
      method: 'PATCH',
      body: JSON.stringify({ edits }),
    }
  );
}

/**
 * Undo the last edit(s).
 * @param conversationId - The conversation ID
 * @returns Undo response with reverted edits
 */
export async function undo(conversationId: string): Promise<UndoRedoResponse> {
  // Backend returns UndoRedoResponse directly
  return request<UndoRedoResponse>(
    `${API_PREFIX}/conversations/${conversationId}/undo`,
    { method: 'POST' }
  );
}

/**
 * Redo the last undone edit(s).
 * @param conversationId - The conversation ID
 * @returns Redo response with reapplied edits
 */
export async function redo(conversationId: string): Promise<UndoRedoResponse> {
  // Backend returns UndoRedoResponse directly
  return request<UndoRedoResponse>(
    `${API_PREFIX}/conversations/${conversationId}/redo`,
    { method: 'POST' }
  );
}

/**
 * Get all fields with their current values.
 * @param conversationId - The conversation ID
 * @returns Fields with values and edit history state
 */
export async function getFields(conversationId: string): Promise<FieldsResponse> {
  // Backend returns FieldValuesResponse directly (not wrapped in ApiResponse)
  // Map backend field format: { conversation_id, fields, can_undo, can_redo }
  const response = await request<{
    conversation_id: string;
    fields: Array<{
      field_id: string;
      value: string | null;
      source: string | null;
      last_modified: string | null;
      bbox: unknown;
    }>;
    can_undo: boolean;
    can_redo: boolean;
  }>(`${API_PREFIX}/conversations/${conversationId}/fields`);

  return {
    fields: response.fields.map(f => ({
      field_id: f.field_id,
      label: f.field_id,
      value: f.value || '',
      type: 'text' as const,
    })),
    history: {
      can_undo: response.can_undo,
      can_redo: response.can_redo,
      undo_count: 0,
      redo_count: 0,
    },
  };
}

/**
 * Get edit history state.
 * @param conversationId - The conversation ID
 * @returns Edit history state with undo/redo availability
 */
export async function getEditHistory(conversationId: string): Promise<EditHistoryState> {
  // Backend returns EditHistoryResponse directly
  const response = await request<{
    conversation_id: string;
    history: { edits: unknown[]; current_index: number };
    total_edits: number;
  }>(`${API_PREFIX}/conversations/${conversationId}/edit-history`);

  return {
    can_undo: response.history.current_index >= 0,
    can_redo: response.history.current_index < response.history.edits.length - 1,
    undo_count: response.history.current_index + 1,
    redo_count: response.history.edits.length - 1 - response.history.current_index,
  };
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
