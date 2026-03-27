const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export interface BBox {
  x: number
  y: number
  width: number
  height: number
}

export interface FormField {
  id: string
  name: string
  field_type: string
  bbox: BBox | null
  page: number
  value: string | null
}

export interface TextBlock {
  id: string
  text: string
  bbox: BBox
  page: number
}

export interface Annotation {
  id: string
  document_id: string
  label_text: string
  label_bbox: BBox
  label_page: number
  field_id: string
  field_name: string
  field_bbox: BBox | null
  field_page: number
  created_at: string | null
}

export interface Mapping {
  id: string
  session_id: string
  annotation_id: string
  field_id: string
  inferred_value: string | null
  confidence: number
  reason: string
}

export interface Form {
  id: string
  document_id: string
  fields: FormField[]
  page_count: number
}

export interface UserInfo {
  data: Record<string, string>
}

export interface Rules {
  items: string[]
}

export type Mode = "preview" | "edit" | "annotate" | "map" | "fill" | "ask" | "rules"

export interface FieldLabelMap {
  id: string
  document_id: string
  field_id: string
  field_name: string
  label_text: string | null
  semantic_key: string | null
  confidence: number
  source: string
}

export interface MapResult {
  document_id: string
  maps: FieldLabelMap[]
}

export interface MapRun {
  created_at: string
  field_count: number
  identified_count: number
}

export interface ContextWindow {
  session_id: string
  document_id: string | null
  form: Form | null
  user_info: UserInfo
  annotations: Annotation[]
  mappings: Mapping[]
  mode: Mode
  history: Array<{ role: string; content: string }>
  rules: Rules
}

export interface AgentQuestion {
  field_id: string
  question: string
  options: string[]
}

export interface FillResult {
  fields: Array<{ field_id: string; value: string }>
  ask: AgentQuestion[]
}

export interface AskResult {
  questions: AgentQuestion[]
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) throw new Error(await res.text())
}

export const formClient = {
  uploadDocument: async (file: File): Promise<{ document_id: string; form: Form }> => {
    const fd = new FormData()
    fd.append("file", file)
    const res = await fetch(`${BASE}/api/documents`, { method: "POST", body: fd })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  getPagePreview: (documentId: string, page: number): string =>
    `${BASE}/api/documents/${documentId}/pages/${page}`,

  getFields: (
    documentId: string
  ): Promise<{ fields: FormField[]; text_blocks: TextBlock[]; page_count: number }> =>
    get(`/api/documents/${documentId}/fields`),

  createSession: (
    documentId?: string,
    userInfo?: UserInfo,
    rules?: Rules
  ): Promise<ContextWindow> =>
    post("/api/sessions", {
      document_id: documentId ?? null,
      user_info: userInfo ?? { data: {} },
      rules: rules ?? { items: [] },
    }),

  updateSessionDocument: (sessionId: string, documentId: string): Promise<ContextWindow> =>
    patch(`/api/sessions/${sessionId}/document`, { document_id: documentId }),

  getSession: (sessionId: string): Promise<ContextWindow> =>
    get(`/api/sessions/${sessionId}`),

  updateUserInfo: (sessionId: string, data: Record<string, string>): Promise<ContextWindow> =>
    patch(`/api/sessions/${sessionId}/user-info`, data),
  createAnnotation: (data: {
    document_id: string
    label_text: string
    label_bbox: BBox
    label_page: number
    field_id: string
    field_name: string
    field_bbox?: BBox
    field_page: number
  }): Promise<Annotation> => post("/api/annotations", data),

  getAnnotations: (documentId: string): Promise<Annotation[]> =>
    get(`/api/annotations/${documentId}`),

  deleteAnnotation: (annotationId: string): Promise<void> =>
    del(`/api/annotations/${annotationId}`),

  runMap: (documentId: string): Promise<MapResult> =>
    post(`/api/map/${documentId}`, {}),

  getMap: (documentId: string): Promise<MapResult> =>
    get(`/api/map/${documentId}`),

  fill: (sessionId: string, userMessage?: string): Promise<FillResult> =>
    post(`/api/fill`, { session_id: sessionId, user_message: userMessage }),

  ask: (sessionId: string): Promise<AskResult> =>
    post(`/api/ask`, { session_id: sessionId }),

  understand: (sessionId: string): Promise<ContextWindow> =>
    post(`/api/sessions/${sessionId}/understand`, {}),

  updateRules: (sessionId: string, items: string[]): Promise<ContextWindow> =>
    patch(`/api/sessions/${sessionId}/rules`, { items }),

  addConversation: (sessionId: string, role: string, content: string): Promise<void> =>
    post(`/api/conversations`, { session_id: sessionId, role, content }),

  listConversations: (sessionId: string): Promise<Array<{ id: string; session_id: string; role: string; content: string; created_at: string | null }>> =>
    get(`/api/conversations/${sessionId}`),
}
