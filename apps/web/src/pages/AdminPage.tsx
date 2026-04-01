import { useState, useEffect, useCallback } from "react"
import { adminClient, type TableInfo } from "../api/adminClient"
import { TableSelector } from "../components/admin/TableSelector"
import { RecordTable } from "../components/admin/RecordTable"
import { RecordDiffPanel } from "../components/admin/RecordDiffPanel"

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debouncedValue
}

export function AdminPage() {
  const [tables, setTables] = useState<TableInfo[]>([])
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [records, setRecords] = useState<Record<string, unknown>[]>([])
  const [columns, setColumns] = useState<string[]>([])
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState("created_at")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")
  const [selectedAId, setSelectedAId] = useState<string | null>(null)
  const [selectedBId, setSelectedBId] = useState<string | null>(null)
  const [recordA, setRecordA] = useState<Record<string, unknown> | null>(null)
  const [recordB, setRecordB] = useState<Record<string, unknown> | null>(null)
  const [showDiff, setShowDiff] = useState(false)
  const [loading, setLoading] = useState(false)

  const debouncedSearch = useDebounce(search, 300)

  useEffect(() => {
    adminClient.listTables().then(setTables).catch(() => {})
  }, [])

  const fetchRecords = useCallback(async () => {
    if (!selectedTable) return
    setLoading(true)
    try {
      const res = await adminClient.listRecords(selectedTable, {
        search: debouncedSearch || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      })
      setRecords(res.records)
      setColumns(res.columns)
    } catch {
      setRecords([])
      setColumns([])
    } finally {
      setLoading(false)
    }
  }, [selectedTable, debouncedSearch, sortBy, sortOrder])

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  const handleTableSelect = useCallback((name: string) => {
    setSelectedTable(name)
    setSelectedAId(null)
    setSelectedBId(null)
    setRecordA(null)
    setRecordB(null)
    setShowDiff(false)
    setSearch("")
    setSortBy("created_at")
    setSortOrder("desc")
  }, [])

  const handleSort = useCallback((column: string) => {
    setSortBy((prev) => {
      if (prev === column) {
        setSortOrder((o) => (o === "asc" ? "desc" : "asc"))
        return prev
      }
      setSortOrder("asc")
      return column
    })
  }, [])

  useEffect(() => {
    if (!selectedTable || !selectedAId || !selectedBId) return
    let cancelled = false
    setLoading(true)
    Promise.all([
      adminClient.getRecord(selectedTable, selectedAId),
      adminClient.getRecord(selectedTable, selectedBId),
    ])
      .then(([a, b]) => {
        if (cancelled) return
        setRecordA(a)
        setRecordB(b)
        setShowDiff(true)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [selectedTable, selectedAId, selectedBId])

  const handleCloseDiff = useCallback(() => {
    setShowDiff(false)
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-6">
        <h1 className="text-lg font-bold text-gray-800">Admin</h1>
        <TableSelector
          tables={tables}
          selected={selectedTable}
          onSelect={handleTableSelect}
        />
        {selectedAId && selectedBId && (
          <span className="ml-auto text-sm text-gray-500">
            Comparing {selectedAId.slice(0, 8)}... vs {selectedBId.slice(0, 8)}...
          </span>
        )}
      </header>

      <main className="p-6">
        {loading && (
          <div className="text-sm text-gray-500 mb-3">Loading...</div>
        )}

        {selectedTable && (
          <RecordTable
            columns={columns}
            records={records}
            search={search}
            onSearchChange={setSearch}
            sortBy={sortBy}
            sortOrder={sortOrder}
            onSort={handleSort}
            selectedAId={selectedAId}
            selectedBId={selectedBId}
            onSelectA={setSelectedAId}
            onSelectB={setSelectedBId}
          />
        )}

        {!selectedTable && (
          <div className="text-center text-gray-400 py-20">
            Select a table to view records
          </div>
        )}
      </main>

      {showDiff && recordA && recordB && (
        <RecordDiffPanel
          recordA={recordA}
          recordB={recordB}
          labelA={selectedAId ?? "A"}
          labelB={selectedBId ?? "B"}
          onClose={handleCloseDiff}
        />
      )}
    </div>
  )
}
