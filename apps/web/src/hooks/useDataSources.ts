/**
 * React hook for managing data sources.
 * Provides state management and API integration for data sources.
 */

import { useState, useCallback, useEffect } from 'react';
import type { DataSourceResponse, ExtractionResult } from '../lib/api-types';
import {
  listDataSources,
  uploadDataSourceFile,
  createTextDataSource,
  deleteDataSource,
  extractFromDataSource,
} from '../api/dataSourceClient';

// ============================================================================
// Types
// ============================================================================

export interface UseDataSourcesState {
  /** List of data sources */
  dataSources: DataSourceResponse[];
  /** Loading state */
  isLoading: boolean;
  /** Upload in progress */
  isUploading: boolean;
  /** Error message */
  error: string | null;
  /** Total count */
  total: number;
}

export interface UseDataSourcesActions {
  /** Upload a file as data source */
  uploadFile: (file: File) => Promise<DataSourceResponse | null>;
  /** Upload multiple files */
  uploadFiles: (files: File[]) => Promise<DataSourceResponse[]>;
  /** Create text data source */
  createText: (name: string, content: string) => Promise<DataSourceResponse | null>;
  /** Delete a data source */
  remove: (dataSourceId: string) => Promise<boolean>;
  /** Refresh the list */
  refresh: () => Promise<void>;
  /** Extract data from a source */
  extract: (dataSourceId: string) => Promise<ExtractionResult | null>;
  /** Clear error */
  clearError: () => void;
}

export interface UseDataSourcesReturn extends UseDataSourcesState, UseDataSourcesActions {}

// ============================================================================
// Hook Implementation
// ============================================================================

export function useDataSources(conversationId: string | null): UseDataSourcesReturn {
  const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Track if we're in local-only mode (no valid conversation on backend)
  const [isLocalOnly, setIsLocalOnly] = useState(false);

  // Fetch data sources on mount and when conversationId changes
  const refresh = useCallback(async () => {
    if (!conversationId) {
      setDataSources([]);
      setTotal(0);
      return;
    }

    // Skip API call if we're in local-only mode
    if (isLocalOnly) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await listDataSources(conversationId);
      setDataSources(response.items);
      setTotal(response.total);
    } catch (err) {
      // Check if this is a "conversation not found" error
      // If so, switch to local-only mode (data sources stored in memory only)
      const errorStr = String(err);
      if (errorStr.includes('CONVERSATION_NOT_FOUND')) {
        console.info('[useDataSources] No conversation found, using local-only mode');
        setIsLocalOnly(true);
        setDataSources([]);
        setTotal(0);
        // Don't set error - this is expected in SinglePage mode
      } else {
        const message = err instanceof Error ? err.message : 'Failed to load data sources';
        setError(message);
        console.error('Failed to fetch data sources:', err);
      }
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, isLocalOnly]);

  // Initial fetch
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Upload a single file
  const uploadFile = useCallback(
    async (file: File): Promise<DataSourceResponse | null> => {
      if (!conversationId) {
        setError('No conversation selected');
        return null;
      }

      setIsUploading(true);
      setError(null);

      // In local-only mode, create a local data source without API
      if (isLocalOnly) {
        const localDs: DataSourceResponse = {
          id: `local-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          type: file.type.includes('pdf') ? 'pdf' :
                file.type.includes('image') ? 'image' :
                file.type.includes('csv') ? 'csv' : 'text',
          name: file.name,
          file_size_bytes: file.size,
          mime_type: file.type,
          created_at: new Date().toISOString(),
        };
        setDataSources((prev) => [localDs, ...prev]);
        setTotal((prev) => prev + 1);
        setIsUploading(false);
        return localDs;
      }

      try {
        const response = await uploadDataSourceFile(conversationId, file);
        // Add to local state
        setDataSources((prev) => [response, ...prev]);
        setTotal((prev) => prev + 1);
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to upload file';
        setError(message);
        console.error('Failed to upload file:', err);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    [conversationId, isLocalOnly]
  );

  // Upload multiple files
  const uploadFiles = useCallback(
    async (files: File[]): Promise<DataSourceResponse[]> => {
      if (!conversationId) {
        setError('No conversation selected');
        return [];
      }

      setIsUploading(true);
      setError(null);

      // In local-only mode, create local data sources without API
      if (isLocalOnly) {
        const localResults: DataSourceResponse[] = files.map((file) => ({
          id: `local-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          type: file.type.includes('pdf') ? 'pdf' as const :
                file.type.includes('image') ? 'image' as const :
                file.type.includes('csv') ? 'csv' as const : 'text' as const,
          name: file.name,
          file_size_bytes: file.size,
          mime_type: file.type,
          created_at: new Date().toISOString(),
        }));
        setDataSources((prev) => [...localResults, ...prev]);
        setTotal((prev) => prev + localResults.length);
        setIsUploading(false);
        return localResults;
      }

      const results: DataSourceResponse[] = [];
      const errors: string[] = [];

      for (const file of files) {
        try {
          const response = await uploadDataSourceFile(conversationId, file);
          results.push(response);
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Failed to upload file';
          errors.push(`${file.name}: ${message}`);
        }
      }

      // Update local state with all successful uploads
      if (results.length > 0) {
        setDataSources((prev) => [...results, ...prev]);
        setTotal((prev) => prev + results.length);
      }

      // Report errors if any
      if (errors.length > 0) {
        setError(errors.join('\n'));
      }

      setIsUploading(false);
      return results;
    },
    [conversationId, isLocalOnly]
  );

  // Create text data source
  const createText = useCallback(
    async (name: string, content: string): Promise<DataSourceResponse | null> => {
      if (!conversationId) {
        setError('No conversation selected');
        return null;
      }

      setIsUploading(true);
      setError(null);

      // In local-only mode, create a local text data source
      if (isLocalOnly) {
        const localDs: DataSourceResponse = {
          id: `local-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          type: 'text',
          name: name,
          content_preview: content.substring(0, 500),
          file_size_bytes: new Blob([content]).size,
          mime_type: 'text/plain',
          created_at: new Date().toISOString(),
        };
        setDataSources((prev) => [localDs, ...prev]);
        setTotal((prev) => prev + 1);
        setIsUploading(false);
        return localDs;
      }

      try {
        const response = await createTextDataSource(conversationId, name, content);
        // Add to local state
        setDataSources((prev) => [response, ...prev]);
        setTotal((prev) => prev + 1);
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to create text data source';
        setError(message);
        console.error('Failed to create text data source:', err);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    [conversationId, isLocalOnly]
  );

  // Delete a data source
  const remove = useCallback(
    async (dataSourceId: string): Promise<boolean> => {
      if (!conversationId) {
        setError('No conversation selected');
        return false;
      }

      setError(null);

      // In local-only mode, just remove from local state
      if (isLocalOnly) {
        setDataSources((prev) => prev.filter((ds) => ds.id !== dataSourceId));
        setTotal((prev) => Math.max(0, prev - 1));
        return true;
      }

      try {
        await deleteDataSource(conversationId, dataSourceId);
        // Remove from local state
        setDataSources((prev) => prev.filter((ds) => ds.id !== dataSourceId));
        setTotal((prev) => Math.max(0, prev - 1));
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to delete data source';
        setError(message);
        console.error('Failed to delete data source:', err);
        return false;
      }
    },
    [conversationId, isLocalOnly]
  );

  // Extract data from a source
  const extract = useCallback(
    async (dataSourceId: string): Promise<ExtractionResult | null> => {
      if (!conversationId) {
        setError('No conversation selected');
        return null;
      }

      setError(null);

      // In local-only mode, extraction is not available (no backend processing)
      if (isLocalOnly) {
        console.info('[useDataSources] Extraction not available in local-only mode');
        return null;
      }

      try {
        const result = await extractFromDataSource(conversationId, dataSourceId);

        // Update local state with extraction results
        setDataSources((prev) =>
          prev.map((ds) =>
            ds.id === dataSourceId
              ? { ...ds, extracted_data: result.extracted_fields }
              : ds
          )
        );

        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to extract data';
        setError(message);
        console.error('Failed to extract data:', err);
        return null;
      }
    },
    [conversationId, isLocalOnly]
  );

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    // State
    dataSources,
    isLoading,
    isUploading,
    error,
    total,
    // Actions
    uploadFile,
    uploadFiles,
    createText,
    remove,
    refresh,
    extract,
    clearError,
  };
}
