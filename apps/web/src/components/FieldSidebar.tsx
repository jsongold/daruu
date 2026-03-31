import type { FormField, Annotation, FieldLabelMap } from "../api/formClient"

interface Props {
  fields: FormField[]
  annotations: Annotation[]
  fieldLabelMaps: FieldLabelMap[]
  currentPage: number
  formId: string | null
}

export function FieldSidebar({ fields, annotations, fieldLabelMaps, currentPage, formId }: Props) {
  const mapByField = new Map(fieldLabelMaps.map((m) => [m.field_id, m]))

  return (
    <aside className="w-56 bg-white border-r border-gray-200 overflow-hidden flex flex-col shrink-0">
      <div className="px-3 py-2 border-b border-gray-200">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Labels &amp; Values
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto">
        {fields.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-8 px-3">
            {formId ? "No fields found." : "Upload a PDF to see fields."}
          </p>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-3 py-1.5 text-gray-500 font-medium w-1/2">Label</th>
                <th className="text-left px-3 py-1.5 text-gray-500 font-medium w-1/2">Value</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => {
                const annotation = annotations.find((a) => a.field_id === f.id)
                const flm = mapByField.get(f.id)
                const label = annotation?.label_text ?? flm?.label_text ?? f.name
                const isAnnotated = !!annotation
                const isMapped = !annotation && !!flm?.label_text
                return (
                  <tr
                    key={f.id}
                    className={[
                      "border-b border-gray-100",
                      f.page === currentPage ? "bg-blue-50/40" : "",
                    ].join(" ")}
                  >
                    <td className="px-3 py-1.5 text-gray-700 truncate max-w-[100px]" title={label}>
                      {label}
                      {isAnnotated && <span className="ml-1 text-[9px] text-blue-500">*</span>}
                      {isMapped && <span className="ml-1 text-[9px] text-indigo-400">~</span>}
                    </td>
                    <td className="px-3 py-1.5 text-green-700 truncate max-w-[100px]" title={f.value ?? ""}>
                      {f.value ?? <span className="text-gray-300">---</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </aside>
  )
}
