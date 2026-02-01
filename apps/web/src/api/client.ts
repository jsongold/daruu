/**
 * Type-safe API client for the Daru PDF backend.
 * Provides functions for all API endpoints with proper error handling.
 */

import type {
  ApiResponse,
  JobContext,
  JobCreate,
  JobResponse,
  RunRequest,
  RunResponse,
  FieldAnswer,
  FieldEdit,
  ReviewResponse,
  Activity,
  EvidenceResponse,
  DocumentResponse,
  DocumentType,
  HealthResponse,
  ReadinessResponse,
  CostDetailedBreakdown,
  RunAsyncRequest,
  RunAsyncResponse,
  TaskStatusResponse,
  AcroFormFieldsResponse,
} from '../types/api';

// ============================================================================
// Configuration
// ============================================================================

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export const getApiBaseUrl = (): string => {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  return DEFAULT_API_BASE_URL;
};

export const apiBaseUrl = getApiBaseUrl();
const API_PREFIX = '/api/v1';

// ============================================================================
// Error Types
// ============================================================================

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status: number,
    public readonly traceId?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }

  static fromResponse(status: number, body: unknown): ApiError {
    if (typeof body === 'object' && body !== null) {
      const error = body as { error?: { code?: string; message?: string; trace_id?: string }; detail?: string };
      const message = error.error?.message || error.detail || 'Unknown error';
      return new ApiError(
        message,
        error.error?.code || 'UNKNOWN',
        status,
        error.error?.trace_id
      );
    }
    if (typeof body === 'string') {
      return new ApiError(body, 'UNKNOWN', status);
    }
    return new ApiError('Unknown error', 'UNKNOWN', status);
  }
}

// ============================================================================
// HTTP Client
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

  // Handle empty responses
  const contentType = response.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T;
  }

  return response.json();
}

async function requestBlob(endpoint: string): Promise<Blob> {
  const url = `${apiBaseUrl}${endpoint}`;
  const response = await fetch(url);

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

  return response.blob();
}

// ============================================================================
// Health API
// ============================================================================

export async function checkHealth(): Promise<HealthResponse> {
  const response = await request<HealthResponse>('/health');
  return response;
}

export async function checkReadiness(): Promise<ReadinessResponse> {
  const response = await request<ReadinessResponse>('/health/ready');
  return response;
}

export async function isApiHealthy(): Promise<boolean> {
  try {
    const health = await checkHealth();
    return health.status === 'healthy';
  } catch {
    return false;
  }
}

// ============================================================================
// Documents API
// ============================================================================

export async function uploadDocument(
  file: File,
  documentType: DocumentType
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);

  const response = await request<ApiResponse<DocumentResponse>>(
    `${API_PREFIX}/documents`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to upload document',
      'UPLOAD_ERROR',
      400
    );
  }

  return response.data;
}

export async function getDocument(documentId: string): Promise<DocumentResponse> {
  const response = await request<ApiResponse<DocumentResponse>>(
    `${API_PREFIX}/documents/${documentId}`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Document not found',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export function getPagePreviewUrl(documentId: string, page: number): string {
  return `${apiBaseUrl}${API_PREFIX}/documents/${documentId}/pages/${page}/preview`;
}

export async function getPagePreviewBlob(documentId: string, page: number): Promise<Blob> {
  return requestBlob(`${API_PREFIX}/documents/${documentId}/pages/${page}/preview`);
}

export async function getAcroFormFields(
  documentId: string
): Promise<AcroFormFieldsResponse> {
  const response = await request<ApiResponse<AcroFormFieldsResponse>>(
    `${API_PREFIX}/documents/${documentId}/acroform-fields`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get AcroForm fields',
      'ACROFORM_ERROR',
      400
    );
  }

  return response.data;
}

// ============================================================================
// Jobs API
// ============================================================================

export async function createJob(data: JobCreate): Promise<JobResponse> {
  const response = await request<ApiResponse<JobResponse>>(
    `${API_PREFIX}/jobs`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to create job',
      'CREATE_ERROR',
      400
    );
  }

  return response.data;
}

export async function getJob(jobId: string): Promise<JobContext> {
  const response = await request<ApiResponse<JobContext>>(
    `${API_PREFIX}/jobs/${jobId}`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Job not found',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export async function runJob(jobId: string, data: RunRequest): Promise<RunResponse> {
  const response = await request<ApiResponse<RunResponse>>(
    `${API_PREFIX}/jobs/${jobId}/run`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to run job',
      'RUN_ERROR',
      400
    );
  }

  return response.data;
}

export async function submitAnswers(
  jobId: string,
  answers: FieldAnswer[]
): Promise<JobContext> {
  const response = await request<ApiResponse<JobContext>>(
    `${API_PREFIX}/jobs/${jobId}/answers`,
    {
      method: 'POST',
      body: JSON.stringify({ answers }),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to submit answers',
      'SUBMIT_ERROR',
      400
    );
  }

  return response.data;
}

/**
 * Update a single field value.
 * Convenience wrapper around submitAnswers for auto-save scenarios.
 */
export async function updateFieldValue(
  jobId: string,
  fieldId: string,
  value: string
): Promise<JobContext> {
  return submitAnswers(jobId, [{ field_id: fieldId, value }]);
}

export async function submitEdits(
  jobId: string,
  edits: FieldEdit[]
): Promise<JobContext> {
  const response = await request<ApiResponse<JobContext>>(
    `${API_PREFIX}/jobs/${jobId}/edits`,
    {
      method: 'POST',
      body: JSON.stringify({ edits }),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to submit edits',
      'SUBMIT_ERROR',
      400
    );
  }

  return response.data;
}

export async function getReview(jobId: string): Promise<ReviewResponse> {
  const response = await request<ApiResponse<ReviewResponse>>(
    `${API_PREFIX}/jobs/${jobId}/review`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get review',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export async function getActivity(jobId: string): Promise<Activity[]> {
  const response = await request<ApiResponse<Activity[]>>(
    `${API_PREFIX}/jobs/${jobId}/activity`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get activity',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export async function getEvidence(
  jobId: string,
  fieldId: string
): Promise<EvidenceResponse> {
  const response = await request<ApiResponse<EvidenceResponse>>(
    `${API_PREFIX}/jobs/${jobId}/evidence?field_id=${encodeURIComponent(fieldId)}`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get evidence',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export async function downloadOutputPdf(jobId: string): Promise<Blob> {
  return requestBlob(`${API_PREFIX}/jobs/${jobId}/output.pdf`);
}

export async function exportJobJson(jobId: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${apiBaseUrl}${API_PREFIX}/jobs/${jobId}/export.json`);
  if (!response.ok) {
    throw new ApiError('Failed to export job', 'EXPORT_ERROR', response.status);
  }
  return response.json();
}

export async function getJobCost(jobId: string): Promise<CostDetailedBreakdown> {
  const response = await request<ApiResponse<CostDetailedBreakdown>>(
    `${API_PREFIX}/jobs/${jobId}/cost`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to get cost',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

// ============================================================================
// Async Task API
// ============================================================================

export async function runJobAsync(
  jobId: string,
  data: RunAsyncRequest
): Promise<RunAsyncResponse> {
  const response = await request<ApiResponse<RunAsyncResponse>>(
    `${API_PREFIX}/jobs/${jobId}/run/async`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to start async job',
      'ASYNC_ERROR',
      400
    );
  }

  return response.data;
}

export async function getTaskStatus(
  jobId: string,
  taskId: string
): Promise<TaskStatusResponse> {
  const response = await request<ApiResponse<TaskStatusResponse>>(
    `${API_PREFIX}/jobs/${jobId}/task/${taskId}`
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Task not found',
      'NOT_FOUND',
      404
    );
  }

  return response.data;
}

export async function cancelTask(
  jobId: string,
  taskId: string
): Promise<{ cancelled: boolean; message: string }> {
  const response = await request<ApiResponse<{ cancelled: boolean; message: string }>>(
    `${API_PREFIX}/jobs/${jobId}/task/${taskId}`,
    { method: 'DELETE' }
  );

  if (!response.success || !response.data) {
    throw new ApiError(
      response.error || 'Failed to cancel task',
      'CANCEL_ERROR',
      400
    );
  }

  return response.data;
}

// ============================================================================
// SSE Events API
// ============================================================================

export interface JobEvent {
  event: string;
  job_id?: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export function subscribeToJobEvents(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const url = `${apiBaseUrl}${API_PREFIX}/jobs/${jobId}/events`;
  const eventSource = new EventSource(url);

  const handleMessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data) as JobEvent;
      onEvent(data);
    } catch (error) {
      if (onError) {
        onError(error instanceof Error ? error : new Error('Failed to parse event'));
      }
    }
  };

  eventSource.addEventListener('connected', handleMessage);
  eventSource.addEventListener('job_started', handleMessage);
  eventSource.addEventListener('step_completed', handleMessage);
  eventSource.addEventListener('status_changed', handleMessage);
  eventSource.addEventListener('field_updated', handleMessage);
  eventSource.addEventListener('job_completed', handleMessage);
  eventSource.addEventListener('ping', handleMessage);
  eventSource.addEventListener('message', handleMessage);

  eventSource.onerror = () => {
    if (onError) {
      onError(new Error('SSE connection error'));
    }
  };

  return () => {
    eventSource.close();
  };
}
