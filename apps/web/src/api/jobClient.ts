const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

// Types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error: any | null;
  meta: any | null;
}

export interface JobContext {
  id: string;
  mode: "transfer" | "scratch";
  status: "running" | "awaiting_input" | "done" | "blocked" | "error";
  source_document?: Document;
  target_document: Document;
  fields: Field[];
  mappings: Mapping[];
  extractions: Extraction[];
  evidence: Evidence[];
  issues: Issue[];
  activities: Activity[];
  created_at: string;
  updated_at: string;
  progress: number;
  current_step: string;
  current_stage: string;
  next_actions: string[];
  iteration_count: number;
}

export interface Document {
  id: string;
  ref: string;
  document_type: "source" | "target";
  meta: DocumentMeta;
  created_at: string;
}

export interface DocumentMeta {
  page_count: number;
  file_size: number;
  mime_type: string;
  filename: string;
  has_password: boolean;
}

export interface Field {
  id: string;
  name: string;
  field_type: "text" | "number" | "date" | "checkbox" | "radio" | "signature";
  value: string | null;
  confidence: number | null;
  bbox: BBox;
  document_id: string;
  page: number;
  is_required: boolean;
  is_editable: boolean;
}

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
  page: number;
}

export interface Mapping {
  id: string;
  source_field_id: string;
  target_field_id: string;
  confidence: number;
}

export interface Extraction {
  id: string;
  field_id: string;
  value: string;
  confidence: number;
  evidence_ids: string[];
}

export interface Evidence {
  id: string;
  field_id: string;
  source: string;
  bbox: BBox;
  confidence: number;
  text: string;
  document_id: string;
}

export interface Issue {
  id: string;
  field_id: string;
  issue_type: string;
  message: string;
  severity: "error" | "warning" | "info";
  suggested_action: string;
}

export interface Activity {
  id: string;
  timestamp: string;
  action: string;
  details: any;
  field_id: string | null;
}

export interface FieldAnswer {
  field_id: string;
  value: string;
}

export interface RunRequest {
  run_mode: "step" | "until_blocked" | "until_done";
  max_steps?: number;
}

export interface RunResponse {
  status: string;
  job_context: JobContext;
  next_actions: string[];
}

// API Functions
export async function getJob(jobId: string): Promise<JobContext> {
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs/${jobId}`);
  
  if (!response.ok) {
    // Try to parse error response
    try {
      const errorResult: ApiResponse<any> = await response.json();
      if (errorResult.error) {
        throw new Error(errorResult.error.message || `Job not found: ${jobId}`);
      }
    } catch {
      // If JSON parsing fails, use status text
    }
    throw new Error(`Failed to get job: ${response.status} ${response.statusText}`);
  }
  
  const result: ApiResponse<JobContext> = await response.json();
  if (!result.success) {
    throw new Error(result.error?.message || "Failed to get job");
  }
  return result.data;
}

export async function runJob(
  jobId: string,
  request: RunRequest
): Promise<RunResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs/${jobId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Failed to run job: ${response.statusText}`);
  }
  const result: ApiResponse<RunResponse> = await response.json();
  if (!result.success) {
    throw new Error(result.error?.message || "Failed to run job");
  }
  return result.data;
}

export async function submitAnswers(
  jobId: string,
  answers: FieldAnswer[]
): Promise<JobContext> {
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs/${jobId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!response.ok) {
    throw new Error(`Failed to submit answers: ${response.statusText}`);
  }
  const result: ApiResponse<JobContext> = await response.json();
  if (!result.success) {
    throw new Error(result.error?.message || "Failed to submit answers");
  }
  return result.data;
}

export async function getPagePreview(
  documentId: string,
  page: number
): Promise<string> {
  const url = `${apiBaseUrl}/api/v1/documents/${documentId}/pages/${page}/preview`;
  console.log("getPagePreview: Fetching", { url, documentId, page });
  
  const response = await fetch(url);
  
  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorData = await response.json();
      if (errorData.error?.message) {
        errorDetail = errorData.error.message;
      } else if (errorData.detail) {
        errorDetail = errorData.detail;
      }
    } catch {
      // If JSON parsing fails, try text
      try {
        const errorText = await response.text();
        if (errorText) {
          errorDetail = errorText;
        }
      } catch {
        // Use status text as fallback
      }
    }
    
    console.error("getPagePreview: Request failed", {
      url,
      status: response.status,
      statusText: response.statusText,
      errorDetail,
    });
    
    throw new Error(`Failed to get preview (${response.status}): ${errorDetail}`);
  }
  
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  console.log("getPagePreview: Success", { url, blobSize: blob.size, objectUrl });
  return objectUrl;
}

export async function downloadOutput(jobId: string): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs/${jobId}/output.pdf`);
  if (!response.ok) {
    throw new Error(`Failed to download output: ${response.statusText}`);
  }
  return await response.blob();
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${apiBaseUrl}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

// Document Upload Types
export interface DocumentUploadResponse {
  document_id: string;
  document_ref: string;
  meta: DocumentMeta;
}

export interface JobCreateRequest {
  mode: "transfer" | "scratch";
  source_document_id?: string;
  target_document_id: string;
}

export interface JobCreateResponse {
  job_id: string;
  job_context: JobContext;
}

// Document Upload Functions
export async function uploadDocument(
  file: File,
  documentType: "source" | "target"
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);

  const response = await fetch(`${apiBaseUrl}/api/v1/documents`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to upload document: ${errorText}`);
  }

  const result: ApiResponse<DocumentUploadResponse> = await response.json();
  if (!result.success) {
    throw new Error(result.error?.message || "Failed to upload document");
  }

  return result.data;
}

// Job Creation Functions
export async function createJob(
  request: JobCreateRequest
): Promise<JobCreateResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to create job: ${errorText}`);
  }

  const result: ApiResponse<JobCreateResponse> = await response.json();
  if (!result.success) {
    throw new Error(result.error?.message || "Failed to create job");
  }

  return result.data;
}
