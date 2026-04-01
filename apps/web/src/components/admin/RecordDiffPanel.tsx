import { useState } from "react"
import ReactDiffViewer from "react-diff-viewer-continued"

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2)
}

function formatRecord(record: Record<string, unknown>): string {
  const allKeys = Object.keys(record)
  return allKeys
    .map((key) => `--- ${key} ---\n${formatValue(record[key])}`)
    .join("\n\n")
}

interface Props {
  recordA: Record<string, unknown>
  recordB: Record<string, unknown>
  labelA: string
  labelB: string
  onClose: () => void
}

export function RecordDiffPanel({ recordA, recordB, labelA, labelB, onClose }: Props) {
  const [splitView, setSplitView] = useState(true)

  const oldValue = formatRecord(recordA)
  const newValue = formatRecord(recordB)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-[90vw] max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 bg-gray-800 text-white rounded-t-lg">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-blue-300 font-medium">A: {labelA}</span>
            <span className="text-gray-400">vs</span>
            <span className="text-green-300 font-medium">B: {labelB}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="px-3 py-1 text-xs rounded bg-gray-600 hover:bg-gray-500 transition-colors"
              onClick={() => setSplitView((prev) => !prev)}
            >
              {splitView ? "Unified" : "Split"}
            </button>
            <button
              className="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-500 transition-colors"
              onClick={onClose}
            >
              Close
            </button>
          </div>
        </div>

        <div className="overflow-auto flex-1 p-2">
          <ReactDiffViewer
            oldValue={oldValue}
            newValue={newValue}
            splitView={splitView}
            leftTitle={labelA}
            rightTitle={labelB}
          />
        </div>
      </div>
    </div>
  )
}
