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
  options: string[]
}

export interface TextBlock {
  id: string
  text: string
  bbox: BBox
  page: number
}

export interface Annotation {
  id: string
  form_id: string
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
  conversation_id: string
  annotation_id: string
  field_id: string
  inferred_value: string | null
  confidence: number
  reason: string
}

export interface Form {
  id: string
  form_id: string
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
  form_id: string
  field_id: string
  field_name: string
  label_text: string | null
  semantic_key: string | null
  confidence: number
  source: string
}

export interface MapResult {
  form_id: string
  maps: FieldLabelMap[]
}

export interface MapRun {
  created_at: string
  field_count: number
  identified_count: number
}

export interface ContextWindow {
  conversation_id: string
  form_id: string | null
  form: Form | null
  user_info: UserInfo
  annotations: Annotation[]
  mappings: Mapping[]
  mode: Mode
  history: Array<{ role: string; content: string }>
  rules: Rules
  form_values: Record<string, string>
}

export interface AgentQuestion {
  field_id: string | null
  question: string
  options: string[]
}

export interface FormSchemaField {
  field_id: string
  field_name: string
  field_type: string
  label_text: string | null
  semantic_key: string | null
  default_value: string | null
  confidence: number
  is_confirmed: boolean
}

export interface FormSchemaResult {
  form_id: string
  form_name: string | null
  fields: FormSchemaField[]
}

export interface FillResult {
  fields: Array<{ field_id: string; value: string }>
  ask: AgentQuestion[]
  schema?: FormSchemaResult
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
  uploadForm: async (file: File): Promise<{ form_id: string; form: Form }> => {
    const fd = new FormData()
    fd.append("file", file)
    const res = await fetch(`${BASE}/api/forms`, { method: "POST", body: fd })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  getPagePreview: (formId: string, page: number): string =>
    `${BASE}/api/forms/${formId}/pages/${page}`,

  getFields: (
    formId: string
  ): Promise<{ fields: FormField[]; text_blocks: TextBlock[]; page_count: number }> =>
    get(`/api/forms/${formId}/fields`),

  createConversation: (
    formId?: string,
    userInfo?: UserInfo,
    rules?: Rules
  ): Promise<ContextWindow> =>
    post("/api/conversations", {
      form_id: formId ?? null,
      user_info: userInfo ?? { data: {} },
      rules: rules ?? { items: [] },
    }),

  updateConversationForm: (conversationId: string, formId: string): Promise<ContextWindow> =>
    patch(`/api/conversations/${conversationId}/form`, { form_id: formId }),

  getConversation: (conversationId: string): Promise<ContextWindow> =>
    get(`/api/conversations/${conversationId}`),

  updateUserInfo: (conversationId: string, data: Record<string, string>): Promise<ContextWindow> =>
    patch(`/api/conversations/${conversationId}/user-info`, data),

  createAnnotation: (data: {
    form_id: string
    label_text: string
    label_bbox: BBox
    label_page: number
    field_id: string
    field_name: string
    field_bbox?: BBox
    field_page: number
  }): Promise<Annotation> => post("/api/annotations", data),

  getAnnotations: (formId: string): Promise<Annotation[]> =>
    get(`/api/annotations/${formId}`),

  deleteAnnotation: (annotationId: string): Promise<void> =>
    del(`/api/annotations/${annotationId}`),

  runMap: (formId: string, conversationId?: string): Promise<MapResult> => {
    const qs = conversationId ? `?conversation_id=${conversationId}` : ""
    return post(`/api/map/${formId}${qs}`, {})
  },

  getMap: (formId: string): Promise<MapResult> =>
    get(`/api/map/${formId}`),

  fill: (conversationId: string, askAnswers?: Record<string, string>): Promise<FillResult> =>
    post(`/api/fill`, { conversation_id: conversationId, ask_answers: askAnswers }),

  ask: (conversationId: string): Promise<AskResult> =>
    post(`/api/ask`, { conversation_id: conversationId }),

  understand: (conversationId: string): Promise<ContextWindow> =>
    post(`/api/conversations/${conversationId}/understand`, {}),

  updateRules: (conversationId: string, items: string[]): Promise<ContextWindow> =>
    patch(`/api/conversations/${conversationId}/rules`, { items }),

  addMessage: (conversationId: string, role: string, content: string): Promise<void> =>
    post(`/api/messages`, { conversation_id: conversationId, role, content }),

  listMessages: (conversationId: string): Promise<Array<{ id: string; conversation_id: string; role: string; content: string; created_at: string | null }>> =>
    get(`/api/messages/${conversationId}`),

  updateFieldValue: (
    conversationId: string,
    fieldId: string,
    value: string,
    fieldName: string,
  ): Promise<ContextWindow> =>
    patch(`/api/conversations/${conversationId}/fields/${fieldId}`, { value, field_name: fieldName }),

  deleteFieldValue: (conversationId: string, fieldId: string, fieldName: string): Promise<void> =>
    del(`/api/conversations/${conversationId}/fields/${fieldId}?field_name=${encodeURIComponent(fieldName)}`),
}
