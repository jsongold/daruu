import { useState, useEffect } from "react"

interface Props {
  rules: string[]
  isLoading: boolean
  onSave: (rules: string[]) => Promise<void>
}

export function RulesPanel({ rules, isLoading, onSave }: Props) {
  const [items, setItems] = useState<string[]>(rules)
  const [isSaving, setIsSaving] = useState(false)
  const [newItem, setNewItem] = useState("")

  // Sync from parent only when Understand populates new rules (not during user editing)
  useEffect(() => {
    if (!isSaving) {
      setItems(rules)
    }
  }, [rules]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleEdit = (index: number, value: string) => {
    setItems((prev) => prev.map((r, i) => (i === index ? value : r)))
  }

  const handleDelete = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  const handleAdd = () => {
    const text = newItem.trim()
    if (!text) return
    setItems((prev) => [...prev, text])
    setNewItem("")
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onSave(items.filter((r) => r.trim()))
    } finally {
      setIsSaving(false)
    }
  }

  const isDirty = JSON.stringify(items) !== JSON.stringify(rules)

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-2 border-b border-gray-200">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Rules</h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          {rules.length} rule{rules.length !== 1 ? "s" : ""} — extracted by agent
        </p>
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div className="flex items-center justify-center gap-2 px-3 py-3 bg-amber-50 border-b border-amber-100">
          <span className="inline-block w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-amber-700">Analyzing document...</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && items.length === 0 && (
        <p className="text-xs text-gray-400 text-center mt-8 px-4">
          Click "Understand" to analyze the document and extract rules.
        </p>
      )}

      {/* Rules list */}
      <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-1.5">
        {items.map((rule, i) => (
          <div key={i} className="flex items-start gap-1.5">
            <span className="text-[10px] text-gray-400 mt-1.5 shrink-0 w-4 text-right">{i + 1}.</span>
            <input
              type="text"
              value={rule}
              onChange={(e) => handleEdit(i, e.target.value)}
              className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400"
            />
            <button
              onClick={() => handleDelete(i)}
              className="shrink-0 text-gray-300 hover:text-red-400 transition-colors text-xs px-1 mt-0.5"
              title="Delete rule"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Add new rule */}
      <div className="px-3 py-2 border-t border-gray-200">
        <div className="flex gap-1.5">
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="Add a rule..."
            className="flex-1 text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:border-blue-400"
          />
          <button
            onClick={handleAdd}
            disabled={!newItem.trim()}
            className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 disabled:opacity-40"
          >
            +
          </button>
        </div>
      </div>

      {/* Save button */}
      {isDirty && (
        <div className="px-3 pb-3">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full px-3 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isSaving ? "Saving..." : "Save Rules"}
          </button>
        </div>
      )}
    </div>
  )
}
