const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export interface TableInfo {
  name: string
  display_name: string
}

export interface RecordsResponse {
  records: Record<string, unknown>[]
  columns: string[]
  total: number
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const adminClient = {
  listTables: (): Promise<TableInfo[]> =>
    get("/api/admin/tables"),

  listRecords: (
    table: string,
    params: {
      search?: string
      sort_by?: string
      sort_order?: string
      limit?: number
      offset?: number
    } = {}
  ): Promise<RecordsResponse> => {
    const qs = new URLSearchParams()
    if (params.search) qs.set("search", params.search)
    if (params.sort_by) qs.set("sort_by", params.sort_by)
    if (params.sort_order) qs.set("sort_order", params.sort_order)
    if (params.limit) qs.set("limit", String(params.limit))
    if (params.offset) qs.set("offset", String(params.offset))
    const q = qs.toString()
    return get(`/api/admin/tables/${table}/records${q ? `?${q}` : ""}`)
  },

  getRecord: (table: string, id: string): Promise<Record<string, unknown>> =>
    get(`/api/admin/tables/${table}/records/${id}`),
}
