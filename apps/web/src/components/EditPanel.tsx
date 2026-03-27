import type { FormField } from "../api/formClient"

interface Props {
  fields: FormField[]
  onValueChange: (fieldId: string, value: string) => void
}

export function EditPanel({ fields, onValueChange }: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200">
        <h2 className="font-semibold text-gray-800 text-sm">Form Fields</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {fields.length} field{fields.length !== 1 ? "s" : ""}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {fields.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">
            No fields detected
          </p>
        )}
        {fields.map((field) => (
          <div key={field.id} className="space-y-1">
            <label className="text-xs font-medium text-gray-600 block truncate">
              {field.name}
              <span className="ml-1 text-gray-400 font-normal">
                ({field.field_type})
              </span>
            </label>
            {field.field_type === "checkbox" ? (
              <input
                type="checkbox"
                checked={field.value === "true" || field.value === "Yes"}
                onChange={(e) =>
                  onValueChange(field.id, e.target.checked ? "true" : "false")
                }
                className="w-4 h-4 text-blue-600 rounded border-gray-300"
              />
            ) : (
              <input
                type="text"
                value={field.value ?? ""}
                onChange={(e) => onValueChange(field.id, e.target.value)}
                placeholder="Enter value..."
                className="w-full px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
