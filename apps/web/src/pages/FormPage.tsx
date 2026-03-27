import { useState, useCallback, useRef, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { formClient } from "../api/formClient"
import type { Form, FormField, TextBlock, Annotation, Mode, AgentQuestion, FieldLabelMap } from "../api/formClient"
import { ModeBar } from "../components/ModeBar"
import { PdfViewer } from "../components/PdfViewer"
import { AnnotatePanel } from "../components/AnnotatePanel"
import { EditPanel } from "../components/EditPanel"
import { AskPanel } from "../components/AskPanel"
import { AskQuestionModal } from "../components/AskQuestionModal"
import { MapPanel } from "../components/MapPanel"
import { ActivityLog } from "../components/InfoChat"
import type { ActivityEntry } from "../components/InfoChat"
import { RulesPanel } from "../components/RulesPanel"
import { useAnnotateMode } from "../hooks/useAnnotateMode"
import { useMapMode } from "../hooks/useMapMode"
import { useRulesMode } from "../hooks/useRulesMode"
import { useFillMode } from "../hooks/useFillMode"
import { usePreviewMode } from "../hooks/usePreviewMode"

export function FormPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [documentId, setDocumentId] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [fields, setFields] = useState<FormField[]>([])
  const [textBlocks, setTextBlocks] = useState<TextBlock[]>([])
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [mode, setMode] = useState<Mode>("preview")
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedLabelId, setSelectedLabelId] = useState<string | null>(null)
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isFilling, setIsFilling] = useState(false)
  const [isAsking, setIsAsking] = useState(false)
  const [isMapping, setIsMapping] = useState(false)
  const [isUnderstanding, setIsUnderstanding] = useState(false)
  const [rulesItems, setRulesItems] = useState<string[]>([])
  const [fieldLabelMaps, setFieldLabelMaps] = useState<FieldLabelMap[]>([])
  const [pendingQuestions, setPendingQuestions] = useState<AgentQuestion[]>([])
  const [askHistory, setAskHistory] = useState<Array<{ role: string; content: string }>>([])
  const [error, setError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [excludedPages, setExcludedPages] = useState<Set<number>>(new Set())
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)

  const addActivity = useCallback((role: ActivityEntry["role"], text: string) => {
    setActivityLog((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role, text, timestamp: new Date().toISOString() },
    ])
  }, [])

  // Restore session from URL
  useEffect(() => {
    if (!urlSessionId) return
    let cancelled = false
    setIsLoading(true)
    setError(null)

    ;(async () => {
      try {
        const ctx = await formClient.getSession(urlSessionId)
        if (cancelled) return
        setSessionId(ctx.session_id)
        setDocumentId(ctx.document_id)
        if (ctx.form) {
          setForm(ctx.form)
          setFields(ctx.form.fields)
        }
        setAnnotations(ctx.annotations)
        setRulesItems(ctx.rules?.items ?? [])
        setMode(ctx.mode as Mode)

        if (ctx.document_id) {
          const fieldsData = await formClient.getFields(ctx.document_id)
          if (cancelled) return
          setTextBlocks(fieldsData.text_blocks)

          if (!ctx.form && fieldsData.fields.length > 0) {
            setFields(fieldsData.fields)
            setForm({
              id: ctx.document_id,
              document_id: ctx.document_id,
              fields: fieldsData.fields,
              page_count: fieldsData.page_count ?? 1,
            })
          }

          const existingAnnotations = await formClient.getAnnotations(ctx.document_id)
          if (cancelled) return
          setAnnotations(existingAnnotations)

          const existingMaps = await formClient.getMap(ctx.document_id)
          if (cancelled) return
          setFieldLabelMaps(existingMaps.maps)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load session")
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [urlSessionId])

  const pageImageUrl = documentId ? formClient.getPagePreview(documentId, currentPage) : null
  const totalPages = form?.page_count ?? 1

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.endsWith(".pdf")) {
      setError("Please upload a PDF file")
      return
    }
    setIsLoading(true)
    setError(null)
    setExcludedPages(new Set())
    try {
      const { document_id, form: uploadedForm } = await formClient.uploadDocument(file)
      setDocumentId(document_id)
      setForm(uploadedForm)
      setFields(uploadedForm.fields)
      setCurrentPage(1)

      const fieldsData = await formClient.getFields(document_id)
      setTextBlocks(fieldsData.text_blocks)

      const session = await formClient.createSession(document_id)
      setSessionId(session.session_id)

      const existingAnnotations = await formClient.getAnnotations(document_id)
      setAnnotations(existingAnnotations)

      const existingMaps = await formClient.getMap(document_id)
      setFieldLabelMaps(existingMaps.maps)

      setMode("preview")
      navigate(`/form/c/${session.session_id}`, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setIsLoading(false)
    }
  }, [navigate])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = ""
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  const handleToggleIncludePage = useCallback((page: number) => {
    setExcludedPages((prev) => {
      const next = new Set(prev)
      if (next.has(page)) next.delete(page)
      else next.add(page)
      return next
    })
  }, [])

  const handleModeChange = useCallback((newMode: Mode) => {
    setMode(newMode)
    setSelectedLabelId(null)
    setSelectedFieldId(null)
  }, [])

  const handleValueChange = useCallback((fieldId: string, value: string) => {
    setFields((prev) => prev.map((f) => (f.id === fieldId ? { ...f, value } : f)))
  }, [])

  // Mode-specific hooks
  const { handleLabelClick, handleFieldClick, handleDeleteAnnotation } = useAnnotateMode({
    mode,
    selectedLabelId,
    documentId,
    textBlocks,
    setAnnotations,
    setSelectedLabelId,
    setSelectedFieldId,
    setIsLoading,
    setError,
  })

  const { handleRunMap } = useMapMode({
    documentId,
    setFieldLabelMaps,
    setIsMapping,
    setError,
    addActivity,
  })

  const { handleUnderstand, handleSaveRules } = useRulesMode({
    sessionId,
    setRulesItems,
    setMode,
    setIsUnderstanding,
    setError,
  })

  const { handleFill, handleAskReply, handleModalSubmit, handleModalClose } = useFillMode({
    sessionId,
    fields,
    pendingQuestions,
    setFields,
    setMode,
    setIsFilling,
    setAskHistory,
    setPendingQuestions,
    setError,
    addActivity,
  })

  const { handleSendInfo, handleAsk } = usePreviewMode({
    sessionId,
    setIsAsking,
    setMode,
    setPendingQuestions,
    setAskHistory,
    setError,
    addActivity,
  })

  // Right panel: declarative mode map
  const rightPanel: Record<Mode, React.ReactNode> = {
    preview: (
      <ActivityLog
        entries={activityLog}
        onSend={handleSendInfo}
        disabled={!sessionId || isFilling}
      />
    ),
    edit: <EditPanel fields={fields} onValueChange={handleValueChange} />,
    annotate: (
      <AnnotatePanel
        annotations={annotations}
        selectedLabelId={selectedLabelId}
        selectedFieldId={selectedFieldId}
        onDelete={handleDeleteAnnotation}
      />
    ),
    map: (
      <MapPanel
        maps={fieldLabelMaps}
        onRunMap={handleRunMap}
        isLoading={isMapping}
        disabled={!documentId}
      />
    ),
    fill: (
      <AskPanel
        history={askHistory}
        onReply={handleAskReply}
        mode={mode}
        isLoading={isFilling || isAsking}
      />
    ),
    ask: (
      <AskPanel
        history={askHistory}
        onReply={handleAskReply}
        mode={mode}
        isLoading={isFilling || isAsking}
      />
    ),
    rules: (
      <RulesPanel
        rules={rulesItems}
        isLoading={isUnderstanding}
        onSave={handleSaveRules}
      />
    ),
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <h1 className="font-bold text-gray-800 text-sm">daru-pdf</h1>
          {documentId && (
            <span className="text-xs text-gray-400 font-mono truncate max-w-[160px]">
              {documentId}
            </span>
          )}
        </div>

        <ModeBar mode={mode} onChange={handleModeChange} disabled={!documentId} />

        <div className="flex items-center gap-2">
          {error && (
            <span className="text-xs text-red-600 max-w-[180px] truncate" title={error}>
              {error}
            </span>
          )}
          <button
            onClick={handleUnderstand}
            disabled={isUnderstanding || isLoading || !sessionId}
            className="px-3 py-1.5 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {isUnderstanding && (
              <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            {isUnderstanding ? "Analyzing..." : "Understand"}
          </button>
          <button
            onClick={handleAsk}
            disabled={isAsking || isLoading || !sessionId}
            className="px-3 py-1.5 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {isAsking && (
              <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            {isAsking ? "Asking..." : "Ask"}
          </button>
          <button
            onClick={() => handleFill()}
            disabled={isFilling || isLoading || !sessionId}
            className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {isFilling && (
              <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            {isFilling ? "Filling..." : "Fill"}
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isFilling}
            className="px-3 py-1.5 text-xs bg-gray-800 text-white rounded hover:bg-gray-700 disabled:opacity-50"
          >
            {isLoading ? "Loading..." : documentId ? "Replace PDF" : "Upload PDF"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileInput}
            className="hidden"
          />
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 bg-white border-r border-gray-200 overflow-hidden flex flex-col shrink-0">
          <div className="px-3 py-2 border-b border-gray-200">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Labels &amp; Values
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {fields.length === 0 ? (
              <p className="text-xs text-gray-400 text-center mt-8 px-3">
                {documentId ? "No fields found." : "Upload a PDF to see fields."}
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
                    return (
                      <tr
                        key={f.id}
                        className={[
                          "border-b border-gray-100",
                          f.page === currentPage ? "bg-blue-50/40" : "",
                        ].join(" ")}
                      >
                        <td className="px-3 py-1.5 text-gray-700 truncate max-w-[100px]" title={annotation?.label_text ?? f.name}>
                          {annotation?.label_text ?? f.name}
                          {annotation && <span className="ml-1 text-[9px] text-blue-500">*</span>}
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

        <main
          className={[
            "flex-1 overflow-hidden",
            isDragging ? "bg-blue-50 border-2 border-dashed border-blue-400" : "",
          ].join(" ")}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <PdfViewer
            imageUrl={pageImageUrl}
            fields={fields}
            textBlocks={textBlocks}
            mode={mode}
            selectedLabelId={selectedLabelId}
            selectedFieldId={selectedFieldId}
            onLabelClick={handleLabelClick}
            onFieldClick={handleFieldClick}
            page={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            excludedPages={excludedPages}
            onToggleIncludePage={handleToggleIncludePage}
          />
        </main>

        <aside className="w-64 bg-white border-l border-gray-200 overflow-hidden flex flex-col shrink-0">
          {rightPanel[mode]}
        </aside>
      </div>

      {pendingQuestions.length > 0 && (
        <AskQuestionModal
          questions={pendingQuestions}
          onSubmit={handleModalSubmit}
          onClose={handleModalClose}
        />
      )}
    </div>
  )
}
