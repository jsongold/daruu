/**
 * Type-safe API client for template endpoints.
 * Provides functions for template matching and selection.
 */

import type { ApiResponse } from '../lib/api-types';
import { apiBaseUrl, ApiError } from './client';

// ============================================================================
// Configuration
// ============================================================================

const API_PREFIX = '/api/v2';

// ============================================================================
// Types
// ============================================================================

/** A form template in the system */
export interface Template {
  /** Unique template ID */
  id: string;
  /** Template display name */
  name: string;
  /** Type of form (e.g., "W-2", "1099", "I-9") */
  form_type: string;
  /** Preview image URL (if available) */
  preview_url: string | null;
  /** Number of fields in the template */
  field_count: number;
}

/** A template match result from visual similarity matching */
export interface TemplateMatch {
  /** Matched template ID */
  template_id: string;
  /** Template display name */
  template_name: string;
  /** Similarity score (0-1) */
  similarity_score: number;
  /** Preview image URL (if available) */
  preview_url: string | null;
  /** Number of fields in the template */
  field_count: number;
}

/** Response from template list endpoint */
export interface TemplateListResponse {
  templates: Template[];
  total: number;
}

/** Response from template match endpoint */
export interface TemplateMatchResponse {
  matches: TemplateMatch[];
  match_duration_ms: number;
}

// ============================================================================
// HTTP Client Helper
// ============================================================================

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${apiBaseUrl}${endpoint}`;

  const defaultHeaders: Record<string, string> = {};
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

  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T;
  }

  return response.json();
}

// ============================================================================
// Templates API
// ============================================================================

/**
 * List all available templates.
 */
export async function listTemplates(): Promise<Template[]> {
  const response = await request<ApiResponse<TemplateListResponse>>(
    `${API_PREFIX}/templates`
  );

  if (!response.success || !response.data) {
    throw new ApiError('Failed to list templates', 'LIST_ERROR', 400);
  }

  return response.data.templates;
}

/**
 * Match templates against a page image.
 * Returns templates sorted by similarity score (highest first).
 */
export async function matchTemplates(pageImage: Blob): Promise<TemplateMatch[]> {
  const formData = new FormData();
  formData.append('page_image', pageImage);

  const response = await request<ApiResponse<TemplateMatchResponse>>(
    `${API_PREFIX}/templates/match`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError('Failed to match templates', 'MATCH_ERROR', 400);
  }

  return response.data.matches;
}

/**
 * Get a single template by ID.
 */
export async function getTemplate(id: string): Promise<Template> {
  const response = await request<ApiResponse<Template>>(
    `${API_PREFIX}/templates/${encodeURIComponent(id)}`
  );

  if (!response.success || !response.data) {
    throw new ApiError('Template not found', 'NOT_FOUND', 404);
  }

  return response.data;
}

/**
 * Get the preview URL for a template.
 */
export function getTemplatePreviewUrl(templateId: string): string {
  return `${apiBaseUrl}${API_PREFIX}/templates/${encodeURIComponent(templateId)}/preview`;
}

// ============================================================================
// Re-exports
// ============================================================================

export type { ApiResponse };
