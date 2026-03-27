import type { FieldLabelMap } from "../api/formClient"

interface Props {
  maps: FieldLabelMap[]
  onRunMap: () => void
  isLoading: boolean
  disabled?: boolean
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const color =
    confidence >= 80 ? "bg-green-100 text-green-700" :
    confidence >= 50 ? "bg-yellow-100 text-yellow-700" :
    "bg-gray-100 text-gray-500"
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${color}`}>
      {confidence}
    </span>
  )
}

export function MapPanel({ maps, onRunMap, isLoading, disabled }: Props) {
  const identified = maps.filter((m) => m.label_text)
  const total = maps.length

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-gray-200">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Field Map
        </h2>
        {total > 0 ? (
          <p className="text-[11px] text-gray-400 mt-0.5">
            {identified.length} / {total} fields identified
          </p>
        ) : (
          <p className="text-[11px] text-gray-400 mt-0.5">
            Run Map to identify field labels
          </p>
        )}
      </div>

      {/* Results table */}
      <div className="flex-1 overflow-y-auto">
        {maps.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-8 px-3">
            No mapping results yet. Click "Run Map" to start.
          </p>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-3 py-1.5 text-gray-500 font-medium">Field</th>
                <th className="text-left px-2 py-1.5 text-gray-500 font-medium">Label</th>
                <th className="px-2 py-1.5 text-gray-500 font-medium text-right">Conf</th>
              </tr>
            </thead>
            <tbody>
              {maps.map((m) => (
                <tr key={m.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-1.5">
                    <div className="text-gray-700 truncate max-w-[80px]" title={m.field_name}>
                      {m.field_name}
                    </div>
                    {m.semantic_key && (
                      <div className="text-[10px] text-blue-400 truncate max-w-[80px]" title={m.semantic_key}>
                        {m.semantic_key}
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-gray-600 truncate max-w-[90px]" title={m.label_text ?? ""}>
                    {m.label_text ?? <span className="text-gray-300 italic">no match</span>}
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    <ConfidenceBadge confidence={m.confidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Run Map button */}
      <div className="p-3 border-t border-gray-200 shrink-0">
        <button
          onClick={onRunMap}
          disabled={isLoading || disabled}
          className="w-full px-3 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading && (
            <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {isLoading ? "Mapping..." : maps.length > 0 ? "Re-run Map" : "Run Map"}
        </button>
      </div>
    </div>
  )
}
