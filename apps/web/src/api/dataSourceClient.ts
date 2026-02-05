/**
 * Type-safe API client for data source endpoints.
 * Provides functions for uploading and managing data sources for AI form filling.
 */

import { apiBaseUrl, ApiError } from './client';
import type {
  DataSourceResponse,
  DataSourceListResponse,
  ExtractionResult,
} from '../lib/api-types';

// ============================================================================
// Types
// ============================================================================

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

  const defaultHeaders: Record<string, string> = {};
  // Don't set Content-Type for FormData - browser will set it with boundary
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

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

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T;
  }

  return response.json();
}

// ============================================================================
// Data Source API Functions
// ============================================================================

/**
 * Upload a file as a data source.
 * @param conversationId - The conversation ID
 * @param file - The file to upload
 * @returns DataSourceResponse with the created data source
 */
export async function uploadDataSourceFile(
  conversationId: string,
  file: File
): Promise<DataSourceResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await request<ApiResponse<DataSourceResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/data-sources`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to upload data source',
      'UPLOAD_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Create a text data source.
 * @param conversationId - The conversation ID
 * @param name - Display name for the text
 * @param content - Text content
 * @returns DataSourceResponse with the created data source
 */
export async function createTextDataSource(
  conversationId: string,
  name: string,
  content: string
): Promise<DataSourceResponse> {
  const formData = new FormData();
  formData.append('text_name', name);
  formData.append('text_content', content);

  const response = await request<ApiResponse<DataSourceResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/data-sources`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to create text data source',
      'CREATE_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * List all data sources for a conversation.
 * @param conversationId - The conversation ID
 * @returns DataSourceListResponse with items and total
 */
export async function listDataSources(
  conversationId: string
): Promise<DataSourceListResponse> {
  const response = await request<ApiResponse<DataSourceListResponse>>(
    `${API_PREFIX}/conversations/${conversationId}/data-sources`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to list data sources',
      'LIST_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Delete a data source.
 * @param conversationId - The conversation ID
 * @param dataSourceId - The data source ID to delete
 */
export async function deleteDataSource(
  conversationId: string,
  dataSourceId: string
): Promise<void> {
  await request<void>(
    `${API_PREFIX}/conversations/${conversationId}/data-sources/${dataSourceId}`,
    {
      method: 'DELETE',
    }
  );
}

/**
 * Trigger extraction from a data source.
 * @param conversationId - The conversation ID
 * @param dataSourceId - The data source ID to extract from
 * @returns ExtractionResult with extracted fields
 */
export async function extractFromDataSource(
  conversationId: string,
  dataSourceId: string
): Promise<ExtractionResult> {
  const response = await request<ApiResponse<ExtractionResult>>(
    `${API_PREFIX}/conversations/${conversationId}/data-sources/${dataSourceId}/extract`,
    {
      method: 'POST',
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to extract from data source',
      'EXTRACTION_ERROR',
      400
    );
  }

  return response.data;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get file type icon based on data source type.
 */
export function getDataSourceIcon(type: string): string {
  switch (type) {
    case 'pdf':
      return '📄';
    case 'image':
      return '🖼️';
    case 'text':
      return '📝';
    case 'csv':
      return '📊';
    default:
      return '📁';
  }
}

/**
 * Format file size for display.
 */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return '';

  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Check if a file type is supported.
 */
export function isSupportedFileType(filename: string): boolean {
  const supportedExtensions = [
    '.pdf',
    '.png',
    '.jpg',
    '.jpeg',
    '.tiff',
    '.tif',
    '.webp',
    '.txt',
    '.csv',
  ];
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return supportedExtensions.includes(ext);
}

/**
 * Get accepted file types for input element.
 */
export function getAcceptedFileTypes(): string {
  return '.pdf,.png,.jpg,.jpeg,.tiff,.tif,.webp,.txt,.csv';
}
