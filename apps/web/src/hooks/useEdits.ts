/**
 * Custom hook for managing field edits with undo/redo support.
 * Handles local state with optimistic updates and server synchronization.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  updateField as apiUpdateField,
  batchUpdateFields as apiBatchUpdateFields,
  undo as apiUndo,
  redo as apiRedo,
  getFields as apiGetFields,
  type FieldEdit,
  type FieldData,
  type EditSource,
  type LocalEditEntry,
  type LocalEditHistory,
  createEmptyHistory,
  generateEditId,
} from '../api/editClient';
import { ApiError } from '../api/client';

// ============================================================================
// Types
// ============================================================================

export interface UseEditsOptions {
  /** Whether to auto-load fields when conversation changes */
  autoLoad?: boolean;
  /** Debounce delay for auto-save (ms) */
  autoSaveDelay?: number;
  /** Maximum undo history size */
  maxHistorySize?: number;
}

export interface UseEditsReturn {
  // State
  /** All fields with current values */
  fields: Record<string, FieldData>;
  /** Fields as array for iteration */
  fieldsArray: FieldData[];
  /** Edit history for undo/redo */
  editHistory: LocalEditHistory;
  /** Whether undo is available */
  canUndo: boolean;
  /** Whether redo is available */
  canRedo: boolean;
  /** Whether a request is in progress */
  isLoading: boolean;
  /** Whether fields are being loaded */
  isLoadingFields: boolean;
  /** Last error message */
  error: string | null;

  // Actions
  /** Update a single field value */
  updateField: (fieldId: string, value: string, source?: EditSource) => Promise<void>;
  /** Update multiple fields at once */
  batchUpdate: (edits: FieldEdit[]) => Promise<void>;
  /** Undo the last edit */
  undo: () => Promise<void>;
  /** Redo the last undone edit */
  redo: () => Promise<void>;
  /** Refresh fields from server */
  refreshFields: () => Promise<void>;
  /** Clear error */
  clearError: () => void;
  /** Get a specific field */
  getField: (fieldId: string) => FieldData | undefined;
  /** Check if a field has been edited */
  isFieldEdited: (fieldId: string) => boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useEdits(
  conversationId: string | null,
  options: UseEditsOptions = {}
): UseEditsReturn {
  const {
    autoLoad = true,
    maxHistorySize = 50,
  } = options;

  // State
  const [fields, setFields] = useState<Record<string, FieldData>>({});
  const [editHistory, setEditHistory] = useState<LocalEditHistory>(createEmptyHistory());
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track original values for edit detection
  const originalValuesRef = useRef<Record<string, string>>({});

  // Computed values
  const canUndo = editHistory.undoStack.length > 0;
  const canRedo = editHistory.redoStack.length > 0;
  const fieldsArray = Object.values(fields);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Get a specific field
  const getField = useCallback((fieldId: string): FieldData | undefined => {
    return fields[fieldId];
  }, [fields]);

  // Check if a field has been edited from original
  const isFieldEdited = useCallback((fieldId: string): boolean => {
    const field = fields[fieldId];
    const original = originalValuesRef.current[fieldId];
    if (!field || original === undefined) return false;
    return field.value !== original;
  }, [fields]);

  // Load fields from server
  const refreshFields = useCallback(async () => {
    if (!conversationId) return;

    setIsLoadingFields(true);
    setError(null);

    try {
      const response = await apiGetFields(conversationId);

      // Convert array to record
      const fieldsRecord: Record<string, FieldData> = {};
      const originalValues: Record<string, string> = {};

      response.fields.forEach((field) => {
        fieldsRecord[field.field_id] = field;
        originalValues[field.field_id] = field.value;
      });

      setFields(fieldsRecord);
      originalValuesRef.current = originalValues;
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to load fields';
      setError(message);
    } finally {
      setIsLoadingFields(false);
    }
  }, [conversationId]);

  // Update a single field
  const updateField = useCallback(async (
    fieldId: string,
    value: string,
    source: EditSource = 'inline'
  ): Promise<void> => {
    if (!conversationId) {
      setError('No active conversation');
      return;
    }

    const existingField = fields[fieldId];
    const oldValue = existingField?.value ?? '';

    // Skip if value unchanged
    if (oldValue === value) return;

    setIsLoading(true);
    setError(null);

    // Optimistic update
    setFields((prev) => ({
      ...prev,
      [fieldId]: {
        ...prev[fieldId],
        value,
      },
    }));

    // Add to undo stack
    const editEntry: LocalEditEntry = {
      id: generateEditId(),
      field_id: fieldId,
      old_value: oldValue,
      new_value: value,
      timestamp: Date.now(),
      source,
    };

    setEditHistory((prev) => {
      const newUndoStack = [...prev.undoStack, editEntry];
      // Trim history if needed
      if (newUndoStack.length > maxHistorySize) {
        newUndoStack.shift();
      }
      return {
        undoStack: newUndoStack,
        redoStack: [], // Clear redo stack on new edit
      };
    });

    try {
      await apiUpdateField(conversationId, fieldId, value, source);
    } catch (err) {
      // Rollback on error
      setFields((prev) => ({
        ...prev,
        [fieldId]: {
          ...prev[fieldId],
          value: oldValue,
        },
      }));

      // Remove from undo stack
      setEditHistory((prev) => ({
        ...prev,
        undoStack: prev.undoStack.filter((e) => e.id !== editEntry.id),
      }));

      const message = err instanceof ApiError ? err.message : 'Failed to update field';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, fields, maxHistorySize]);

  // Batch update multiple fields
  const batchUpdate = useCallback(async (edits: FieldEdit[]): Promise<void> => {
    if (!conversationId) {
      setError('No active conversation');
      return;
    }

    if (edits.length === 0) return;

    setIsLoading(true);
    setError(null);

    // Store old values for rollback
    const oldValues: Record<string, string> = {};
    const editEntries: LocalEditEntry[] = [];

    edits.forEach((edit) => {
      const existingField = fields[edit.field_id];
      const oldValue = existingField?.value ?? '';
      oldValues[edit.field_id] = oldValue;

      editEntries.push({
        id: generateEditId(),
        field_id: edit.field_id,
        old_value: oldValue,
        new_value: edit.value,
        timestamp: Date.now(),
        source: edit.source,
      });
    });

    // Optimistic update
    setFields((prev) => {
      const updated = { ...prev };
      edits.forEach((edit) => {
        if (updated[edit.field_id]) {
          updated[edit.field_id] = {
            ...updated[edit.field_id],
            value: edit.value,
          };
        }
      });
      return updated;
    });

    // Add to undo stack
    setEditHistory((prev) => {
      const newUndoStack = [...prev.undoStack, ...editEntries];
      // Trim history if needed
      while (newUndoStack.length > maxHistorySize) {
        newUndoStack.shift();
      }
      return {
        undoStack: newUndoStack,
        redoStack: [], // Clear redo stack on new edit
      };
    });

    try {
      await apiBatchUpdateFields(conversationId, edits);
    } catch (err) {
      // Rollback on error
      setFields((prev) => {
        const updated = { ...prev };
        Object.entries(oldValues).forEach(([fieldId, oldValue]) => {
          if (updated[fieldId]) {
            updated[fieldId] = {
              ...updated[fieldId],
              value: oldValue,
            };
          }
        });
        return updated;
      });

      // Remove from undo stack
      const editIds = new Set(editEntries.map((e) => e.id));
      setEditHistory((prev) => ({
        ...prev,
        undoStack: prev.undoStack.filter((e) => !editIds.has(e.id)),
      }));

      const message = err instanceof ApiError ? err.message : 'Failed to batch update fields';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, fields, maxHistorySize]);

  // Undo the last edit
  const undo = useCallback(async (): Promise<void> => {
    if (!conversationId || editHistory.undoStack.length === 0) return;

    setIsLoading(true);
    setError(null);

    const lastEdit = editHistory.undoStack[editHistory.undoStack.length - 1];

    // Optimistic update
    setFields((prev) => ({
      ...prev,
      [lastEdit.field_id]: {
        ...prev[lastEdit.field_id],
        value: lastEdit.old_value,
      },
    }));

    // Move from undo to redo stack
    setEditHistory((prev) => ({
      undoStack: prev.undoStack.slice(0, -1),
      redoStack: [...prev.redoStack, lastEdit],
    }));

    try {
      await apiUndo(conversationId);
    } catch (err) {
      // Rollback on error
      setFields((prev) => ({
        ...prev,
        [lastEdit.field_id]: {
          ...prev[lastEdit.field_id],
          value: lastEdit.new_value,
        },
      }));

      // Restore undo stack
      setEditHistory((prev) => ({
        undoStack: [...prev.undoStack, lastEdit],
        redoStack: prev.redoStack.slice(0, -1),
      }));

      const message = err instanceof ApiError ? err.message : 'Failed to undo';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, editHistory]);

  // Redo the last undone edit
  const redo = useCallback(async (): Promise<void> => {
    if (!conversationId || editHistory.redoStack.length === 0) return;

    setIsLoading(true);
    setError(null);

    const lastUndo = editHistory.redoStack[editHistory.redoStack.length - 1];

    // Optimistic update
    setFields((prev) => ({
      ...prev,
      [lastUndo.field_id]: {
        ...prev[lastUndo.field_id],
        value: lastUndo.new_value,
      },
    }));

    // Move from redo to undo stack
    setEditHistory((prev) => ({
      undoStack: [...prev.undoStack, lastUndo],
      redoStack: prev.redoStack.slice(0, -1),
    }));

    try {
      await apiRedo(conversationId);
    } catch (err) {
      // Rollback on error
      setFields((prev) => ({
        ...prev,
        [lastUndo.field_id]: {
          ...prev[lastUndo.field_id],
          value: lastUndo.old_value,
        },
      }));

      // Restore redo stack
      setEditHistory((prev) => ({
        undoStack: prev.undoStack.slice(0, -1),
        redoStack: [...prev.redoStack, lastUndo],
      }));

      const message = err instanceof ApiError ? err.message : 'Failed to redo';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, editHistory]);

  // Auto-load fields when conversation changes
  useEffect(() => {
    if (autoLoad && conversationId) {
      // Reset state
      setFields({});
      setEditHistory(createEmptyHistory());
      originalValuesRef.current = {};

      refreshFields();
    }
  }, [autoLoad, conversationId, refreshFields]);

  // Clear state when conversation is cleared
  useEffect(() => {
    if (!conversationId) {
      setFields({});
      setEditHistory(createEmptyHistory());
      originalValuesRef.current = {};
      setError(null);
    }
  }, [conversationId]);

  return {
    // State
    fields,
    fieldsArray,
    editHistory,
    canUndo,
    canRedo,
    isLoading,
    isLoadingFields,
    error,

    // Actions
    updateField,
    batchUpdate,
    undo,
    redo,
    refreshFields,
    clearError,
    getField,
    isFieldEdited,
  };
}
