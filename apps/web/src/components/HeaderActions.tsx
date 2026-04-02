interface Props {
  formId: string | null
  conversationId: string | null
  isLoading: boolean
  isFilling: boolean
  isAsking: boolean
  isMapping: boolean
  isUnderstanding: boolean
  isSegmenting: boolean
  error: string | null
  onUnderstand: () => void
  onSegment: () => void
  onMap: () => void
  onAsk: () => void
  onFill: () => void
  onUploadClick: () => void
}

function Spinner() {
  return (
    <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
  )
}

export function HeaderActions({
  formId, conversationId,
  isLoading, isFilling, isAsking, isMapping, isUnderstanding, isSegmenting,
  error,
  onUnderstand, onSegment, onMap, onAsk, onFill, onUploadClick,
}: Props) {
  const busy = isLoading || isFilling

  return (
    <div className="flex items-center gap-2">
      {error && (
        <span className="text-xs text-red-600 max-w-[180px] truncate" title={error}>
          {error}
        </span>
      )}
      <button
        onClick={onUnderstand}
        disabled={isUnderstanding || busy || !conversationId}
        className="px-3 py-1.5 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
      >
        {isUnderstanding && <Spinner />}
        {isUnderstanding ? "Analyzing..." : "Understand"}
      </button>
      <button
        onClick={onMap}
        disabled={isMapping || busy || !conversationId}
        className="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
      >
        {isMapping && <Spinner />}
        {isMapping ? "Mapping..." : "Map"}
      </button>
      <button
        onClick={onSegment}
        disabled={isSegmenting || busy || !formId}
        className="px-3 py-1.5 text-xs bg-teal-600 text-white rounded hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
      >
        {isSegmenting && <Spinner />}
        {isSegmenting ? "Segmenting..." : "Segment"}
      </button>
      <button
        onClick={onAsk}
        disabled={isAsking || busy || !conversationId}
        className="px-3 py-1.5 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
      >
        {isAsking && <Spinner />}
        {isAsking ? "Asking..." : "Ask"}
      </button>
      <button
        onClick={onFill}
        disabled={isFilling || busy || !conversationId}
        className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
      >
        {isFilling && <Spinner />}
        {isFilling ? "Filling..." : "Fill"}
      </button>
      <button
        onClick={onUploadClick}
        disabled={busy}
        className="px-3 py-1.5 text-xs bg-gray-800 text-white rounded hover:bg-gray-700 disabled:opacity-50"
      >
        {isLoading ? "Loading..." : formId ? "Replace PDF" : "Upload PDF"}
      </button>
    </div>
  )
}
