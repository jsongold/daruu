import type { TableInfo } from "../../api/adminClient"

interface Props {
  tables: TableInfo[]
  selected: string | null
  onSelect: (name: string) => void
}

export function TableSelector({ tables, selected, onSelect }: Props) {
  return (
    <select
      className="bg-white border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      value={selected ?? ""}
      onChange={(e) => onSelect(e.target.value)}
    >
      <option value="" disabled>
        Select a table...
      </option>
      {tables.map((t) => (
        <option key={t.name} value={t.name}>
          {t.display_name}
        </option>
      ))}
    </select>
  )
}
