import type { Annotation } from "../api/formClient"

interface Props {
  annotations: Annotation[]
  selectedLabelId: string | null
  selectedFieldId: string | null
  onDelete: (id: string) => void
}

export function AnnotatePanel({
  annotations,
  selectedLabelId,
  selectedFieldId,
  onDelete,
}: Props) {
  const pendingState = selectedLabelId
    ? selectedFieldId
      ? null
      : "Now select a field on the PDF..."
    : "Select a text label on the PDF to start an annotation pair"

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200">
        <h2 className="font-semibold text-gray-800 text-sm">Annotations</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {annotations.length} pair{annotations.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Pending selection hint */}
      {pendingState && (
        <div className="mx-3 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
          {pendingState}
        </div>
      )}

      {/* Annotation list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {annotations.length === 0 && !pendingState && (
          <p className="text-xs text-gray-400 text-center mt-8">
            No annotations yet
          </p>
        )}
        {annotations.map((ann) => (
          <div
            key={ann.id}
            className="flex items-start gap-2 p-2 bg-white border border-gray-200 rounded hover:border-gray-300 transition-colors"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 text-xs">
                <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded font-medium truncate max-w-[120px]">
                  {ann.label_text}
                </span>
                <span className="text-gray-400 shrink-0">→</span>
                <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium truncate max-w-[120px]">
                  {ann.field_name}
                </span>
              </div>
              <div className="text-[10px] text-gray-400 mt-0.5">
                p{ann.label_page} → p{ann.field_page}
              </div>
            </div>
            <button
              onClick={() => onDelete(ann.id)}
              className="shrink-0 text-gray-300 hover:text-red-400 transition-colors text-xs px-1"
              title="Delete annotation"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
