import { useState, useEffect } from "react"
import type { FormField, TextBlock, Mode, BBox } from "../api/formClient"

interface Props {
  imageUrl: string | null
  fields: FormField[]
  textBlocks: TextBlock[]
  mode: Mode
  selectedLabelId: string | null
  selectedFieldId: string | null
  onLabelClick: (block: TextBlock) => void
  onFieldClick: (field: FormField) => void
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  excludedPages: Set<number>
  onToggleIncludePage: (page: number) => void
}

function bboxStyle(bbox: BBox) {
  return {
    left: `${bbox.x * 100}%`,
    top: `${bbox.y * 100}%`,
    width: `${bbox.width * 100}%`,
    height: `${bbox.height * 100}%`,
  }
}

export function PdfViewer({
  imageUrl,
  fields,
  textBlocks,
  mode,
  selectedLabelId,
  selectedFieldId,
  onLabelClick,
  onFieldClick,
  page,
  totalPages,
  onPageChange,
  excludedPages,
  onToggleIncludePage,
}: Props) {
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!imageUrl) {
      setResolvedUrl(null)
      return
    }
    // If imageUrl is an endpoint URL (not a data URL), fetch the image_url from it
    if (!imageUrl.startsWith("data:")) {
      fetch(imageUrl)
        .then((r) => r.json())
        .then((data: { image_url?: string }) => {
          setResolvedUrl(data.image_url ?? null)
        })
        .catch(() => setResolvedUrl(null))
    } else {
      setResolvedUrl(imageUrl)
    }
  }, [imageUrl])

  const currentPageFields = fields.filter((f) => f.page === page)
  const currentPageBlocks = textBlocks.filter((b) => b.page === page)

  return (
    <div className="flex flex-col h-full">
      {/* PDF Page Image with overlays */}
      <div className="flex-1 overflow-auto flex items-start justify-center p-4">
        <div className={["relative inline-block max-w-full", excludedPages.has(page) ? "opacity-40" : ""].join(" ")}>
          {resolvedUrl ? (
            <img
              src={resolvedUrl}
              alt={`Page ${page}`}
              className="max-w-full h-auto block"
              draggable={false}
            />
          ) : (
            <div className="w-[600px] h-[800px] bg-gray-100 flex items-center justify-center text-gray-400">
              {imageUrl ? "Loading..." : "Upload a PDF to get started"}
            </div>
          )}

          {/* Field overlays */}
          {resolvedUrl &&
            currentPageFields.map((field) => {
              if (!field.bbox) return null
              const isSelected = selectedFieldId === field.id
              const borderColor =
                mode === "annotate" && isSelected
                  ? "border-blue-500 bg-blue-100/30"
                  : mode === "annotate"
                  ? "border-blue-300/60 hover:border-blue-500 hover:bg-blue-50/20"
                  : mode === "edit"
                  ? "border-orange-400/70 hover:border-orange-500"
                  : mode === "preview" || mode === "fill" || mode === "ask"
                  ? "border-green-400/50"
                  : "border-gray-300/50"

              return (
                <div
                  key={field.id}
                  className={`absolute border-2 cursor-pointer transition-colors ${borderColor}`}
                  style={bboxStyle(field.bbox)}
                  onClick={() => onFieldClick(field)}
                  title={field.name}
                >
                  {field.value && (
                    <span className="absolute inset-0 flex items-center px-0.5 text-[10px] text-green-800 overflow-hidden whitespace-nowrap">
                      {field.value}
                    </span>
                  )}
                  {mode === "edit" && (
                    <span className="absolute -top-4 left-0 text-[9px] bg-orange-100 px-1 text-orange-700 whitespace-nowrap max-w-[120px] truncate">
                      {field.name}
                    </span>
                  )}
                </div>
              )
            })}

          {/* Text block overlays (annotate mode only) */}
          {resolvedUrl &&
            mode === "annotate" &&
            currentPageBlocks.map((block) => {
              const isSelected = selectedLabelId === block.id
              return (
                <div
                  key={block.id}
                  className={[
                    "absolute border-2 cursor-pointer transition-colors",
                    isSelected
                      ? "border-green-500 bg-green-100/40"
                      : "border-green-300/60 hover:border-green-500 hover:bg-green-50/30",
                  ].join(" ")}
                  style={bboxStyle(block.bbox)}
                  onClick={() => onLabelClick(block)}
                  title={block.text}
                />
              )
            })}
        </div>
      </div>

      {/* Footer: page nav + exclude */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 bg-white text-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
          >
            ← Prev
          </button>
          <span className="text-gray-600">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
          >
            Next →
          </button>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none text-gray-600">
          <input
            type="checkbox"
            checked={!excludedPages.has(page)}
            onChange={() => onToggleIncludePage(page)}
            className="w-4 h-4 accent-blue-500"
          />
          Include page
        </label>
      </div>
    </div>
  )
}
