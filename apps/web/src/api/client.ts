import type { TemplateSchema } from "../lib/schema";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

const ANALYZE_TIMEOUT_MS = 300000; // 5 minutes

type GeneratePdfRequest = {
  schema_json: TemplateSchema;
  data: Record<string, string>;
};

async function postFormDataWithTimeout(
  url: string,
  formData: FormData,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function analyzeTemplateFromFile(file: File): Promise<TemplateSchema> {
  const formData = new FormData();
  formData.append("file", file);

  console.info("API request: analyze (file)", {
    name: file.name,
    size: file.size,
    type: file.type,
  });
  const response = await postFormDataWithTimeout(
    `${apiBaseUrl}/analyze`,
    formData,
    ANALYZE_TIMEOUT_MS,
  );
  console.info("API response: analyze (file)", {
    status: response.status,
    ok: response.ok,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to analyze template: ${detail}`);
  }

  const data = (await response.json()) as { schema_json: TemplateSchema };
  return data.schema_json;
}

export async function analyzeTemplateFromUrl(
  pdfUrl: string,
): Promise<TemplateSchema> {
  const formData = new FormData();
  formData.append("pdf_url", pdfUrl);

  console.info("API request: analyze (url)", { pdfUrl });
  const response = await postFormDataWithTimeout(
    `${apiBaseUrl}/analyze`,
    formData,
    ANALYZE_TIMEOUT_MS,
  );
  console.info("API response: analyze (url)", {
    status: response.status,
    ok: response.ok,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to analyze template: ${detail}`);
  }

  const data = (await response.json()) as { schema_json: TemplateSchema };
  return data.schema_json;
}

export async function generatePdfPreview(
  payload: GeneratePdfRequest,
): Promise<Blob> {
  const response = await fetch(`${apiBaseUrl}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Failed to generate PDF: ${detail}`);
  }

  return await response.blob();
}
