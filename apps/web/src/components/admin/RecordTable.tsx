interface Props {
  columns: string[]
  records: Record<string, unknown>[]
  search: string
  onSearchChange: (value: string) => void
  sortBy: string
  sortOrder: "asc" | "desc"
  onSort: (column: string) => void
  selectedAId: string | null
  selectedBId: string | null
  onSelectA: (id: string) => void
  onSelectB: (id: string) => void
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "object") {
    const json = JSON.stringify(value)
    return json.length > 80 ? json.slice(0, 80) + "..." : json
  }
  const str = String(value)
  return str.length > 80 ? str.slice(0, 80) + "..." : str
}

function getRecordId(record: Record<string, unknown>): string {
  return String(record.id ?? record.ID ?? "")
}

function SortArrow({ column, sortBy, sortOrder }: { column: string; sortBy: string; sortOrder: "asc" | "desc" }) {
  if (column !== sortBy) return null
  return <span className="ml-1">{sortOrder === "asc" ? "\u25B2" : "\u25BC"}</span>
}

export function RecordTable({
  columns,
  records,
  search,
  onSearchChange,
  sortBy,
  sortOrder,
  onSort,
  selectedAId,
  selectedBId,
  onSelectA,
  onSelectB,
}: Props) {
  return (
    <div className="flex flex-col gap-3">
      <input
        type="text"
        placeholder="Search records..."
        className="border border-gray-300 rounded px-3 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
      />

      <div className="overflow-auto max-h-[60vh] border border-gray-200 rounded">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 bg-gray-100 z-10">
            <tr>
              <th className="px-2 py-2 text-left text-xs font-semibold text-blue-700 border-b border-gray-200">
                A
              </th>
              <th className="px-2 py-2 text-left text-xs font-semibold text-green-700 border-b border-gray-200">
                B
              </th>
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-xs font-semibold text-gray-600 border-b border-gray-200 cursor-pointer hover:text-gray-900 select-none whitespace-nowrap"
                  onClick={() => onSort(col)}
                >
                  {col}
                  <SortArrow column={col} sortBy={sortBy} sortOrder={sortOrder} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {records.map((record, idx) => {
              const id = getRecordId(record)
              return (
                <tr
                  key={id || idx}
                  className={`${idx % 2 === 0 ? "bg-white" : "bg-gray-50"} hover:bg-blue-50 transition-colors`}
                >
                  <td className="px-2 py-1.5 border-b border-gray-100">
                    <input
                      type="radio"
                      name="record-a"
                      checked={selectedAId === id}
                      onChange={() => onSelectA(id)}
                      className="accent-blue-600"
                    />
                  </td>
                  <td className="px-2 py-1.5 border-b border-gray-100">
                    <input
                      type="radio"
                      name="record-b"
                      checked={selectedBId === id}
                      onChange={() => onSelectB(id)}
                      className="accent-green-600"
                    />
                  </td>
                  {columns.map((col) => (
                    <td
                      key={col}
                      className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap max-w-xs truncate"
                      title={String(record[col] ?? "")}
                    >
                      {formatCell(record[col])}
                    </td>
                  ))}
                </tr>
              )
            })}
            {records.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length + 2}
                  className="px-3 py-8 text-center text-gray-400"
                >
                  No records found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
