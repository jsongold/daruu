import { useState } from "react"
import type { FormField, Annotation, FieldLabelMap, Mode } from "../api/formClient"

interface Props {
  mode: Mode
  fields: FormField[]
  annotations: Annotation[]
  fieldLabelMaps: FieldLabelMap[]
  selectedLabelId: string | null
  selectedFieldId: string | null
  currentPage: number
  formId: string | null
  onValueChange: (fieldId: string, value: string) => void
  onDeleteAnnotation: (id: string) => void
}

function SectionHeader({
  title,
  count,
  open,
  onToggle,
}: {
  title: string
  count?: number
  open: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full flex items-center justify-between px-3 py-1.5 bg-gray-50 border-b border-gray-200 hover:bg-gray-100 transition-colors"
    >
      <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        {title}
        {count !== undefined && (
          <span className="ml-1.5 text-[10px] font-normal text-gray-400 normal-case">({count})</span>
        )}
      </span>
      <span className="text-gray-400 text-xs">{open ? "▾" : "▸"}</span>
    </button>
  )
}


export function LeftPanel({
  mode,
  fields,
  annotations,
  fieldLabelMaps,
  selectedLabelId,
  selectedFieldId,
  currentPage,
  formId,
  onValueChange,
  onDeleteAnnotation,
}: Props) {
  const [fieldsOpen, setFieldsOpen] = useState(true)
  const [annotationsOpen, setAnnotationsOpen] = useState(true)

  const mapByField = new Map(fieldLabelMaps.map((m) => [m.field_id, m]))
  const isEdit = mode === "edit"

  const pendingState = selectedLabelId
    ? selectedFieldId
      ? null
      : "Now select a field on the PDF..."
    : mode === "annotate"
      ? "Select a text label on the PDF to start an annotation pair"
      : null

  return (
    <aside className="w-72 bg-white border-r border-gray-200 overflow-hidden flex flex-col shrink-0">
      {/* Fields section — labels updated by map results */}
      <SectionHeader
        title="Fields"
        count={fields.length}
        open={fieldsOpen}
        onToggle={() => setFieldsOpen((v) => !v)}
      />
      {fieldsOpen && (
        <div className="flex-1 overflow-y-auto">
          {fields.length === 0 ? (
            <p className="text-xs text-gray-400 text-center mt-6 px-3">
              {formId ? "No fields found." : "Upload a PDF to see fields."}
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-2 py-1.5 text-gray-500 font-medium">Label</th>
                  <th className="text-left px-2 py-1.5 text-gray-500 font-medium">Value</th>
                  <th className="text-center px-1 py-1.5 text-gray-500 font-medium w-10">Conf</th>
                  <th className="text-left px-1 py-1.5 text-gray-500 font-medium w-12">Source</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((f) => {
                  const annotation = annotations.find((a) => a.field_id === f.id)
                  const flm = mapByField.get(f.id)
                  const label = annotation?.label_text ?? flm?.label_text ?? f.name
                  const isAnnotated = !!annotation
                  const isMapped = !annotation && !!flm?.label_text
                  const conf = flm?.confidence ?? null
                  const by = isAnnotated ? "user" : flm?.source ?? null
                  return (
                    <tr
                      key={f.id}
                      className={[
                        "border-b border-gray-100",
                        f.page === currentPage ? "bg-blue-50/40" : "",
                      ].join(" ")}
                    >
                      <td className="px-2 py-1.5 text-gray-700 truncate max-w-[70px]" title={label}>
                        {label}
                        {isAnnotated && <span className="ml-1 text-[9px] text-blue-500">*</span>}
                        {isMapped && <span className="ml-1 text-[9px] text-indigo-400">~</span>}
                      </td>
                      <td className="px-2 py-1.5 max-w-[60px]">
                        {isEdit ? (
                          <input
                            type="text"
                            value={f.value ?? ""}
                            onChange={(e) => onValueChange(f.id, e.target.value)}
                            className="w-full text-xs text-green-700 bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-400 focus:outline-none truncate"
                            placeholder="---"
                          />
                        ) : (
                          <span className="text-green-700 truncate block" title={f.value ?? ""}>
                            {f.value ?? <span className="text-gray-300">---</span>}
                          </span>
                        )}
                      </td>
                      <td className="px-1 py-1.5 text-center">
                        {conf !== null ? (
                          <span
                            className={[
                              "text-[10px] font-mono",
                              conf >= 80 ? "text-green-600" : conf >= 50 ? "text-amber-600" : "text-red-500",
                            ].join(" ")}
                            title={`Confidence: ${Math.round(conf)}%`}
                          >
                            {Math.round(conf)}
                          </span>
                        ) : (
                          <span className="text-gray-300 text-[10px]">-</span>
                        )}
                      </td>
                      <td className="px-1 py-1.5">
                        {by ? (
                          <span className="text-[10px] text-gray-500 truncate block" title={by}>
                            {by}
                          </span>
                        ) : (
                          <span className="text-gray-300 text-[10px]">-</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Annotations section */}
      <SectionHeader
        title="Annotations"
        count={annotations.length}
        open={annotationsOpen}
        onToggle={() => setAnnotationsOpen((v) => !v)}
      />
      {annotationsOpen && (
        <div className="overflow-y-auto max-h-48 shrink-0">
          {pendingState && (
            <div className="mx-2 mt-2 px-2 py-1.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
              {pendingState}
            </div>
          )}
          {annotations.length === 0 && !pendingState ? (
            <p className="text-xs text-gray-400 text-center mt-6 px-3">No annotations yet</p>
          ) : (
            <div className="p-2 space-y-1.5">
              {annotations.map((ann) => (
                <div
                  key={ann.id}
                  className="flex items-start gap-1.5 p-1.5 bg-white border border-gray-200 rounded hover:border-gray-300 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 text-xs flex-wrap">
                      <span className="px-1 py-0.5 bg-green-100 text-green-700 rounded font-medium truncate max-w-[70px]">
                        {ann.label_text}
                      </span>
                      <span className="text-gray-400 shrink-0">→</span>
                      <span className="px-1 py-0.5 bg-blue-100 text-blue-700 rounded font-medium truncate max-w-[70px]">
                        {ann.field_name}
                      </span>
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">
                      p{ann.label_page} → p{ann.field_page}
                    </div>
                  </div>
                  <button
                    onClick={() => onDeleteAnnotation(ann.id)}
                    className="shrink-0 text-gray-300 hover:text-red-400 transition-colors text-xs px-0.5"
                    title="Delete annotation"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  )
}
