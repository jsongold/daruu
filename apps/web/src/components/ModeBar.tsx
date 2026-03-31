import type { Mode } from "../api/formClient"

interface Props {
  mode: Mode
  onChange: (mode: Mode) => void
  disabled?: boolean
}

const MODE_LABELS: Record<Mode, string> = {
  preview: "Preview",
  edit: "Edit",
  annotate: "Annotate/Map",
  map: "Map",
  fill: "Fill",
  ask: "Ask",
  rules: "Rules",
}

const USER_MODES: Mode[] = ["edit", "annotate"]

export function ModeBar({ mode, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-1 bg-gray-100 rounded-full px-2 py-1">
      {USER_MODES.map((m) => (
        <button
          key={m}
          onClick={() => onChange(m)}
          disabled={disabled}
          className={[
            "px-3 py-1 rounded-full text-sm font-medium transition-colors",
            mode === m
              ? "bg-blue-600 text-white shadow-sm"
              : "text-gray-600 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed",
          ].join(" ")}
        >
          {MODE_LABELS[m]}
        </button>
      ))}
    </div>
  )
}
