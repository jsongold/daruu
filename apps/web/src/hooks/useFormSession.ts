import { useState, useCallback, useRef, useEffect } from "react"
import type { NavigateFunction } from "react-router-dom"
import { formClient } from "../api/formClient"
import type { Form, FormField, TextBlock, Annotation, Mode, AgentQuestion, FieldLabelMap } from "../api/formClient"
import { useChatWindow } from "./useChatWindow"

export function useFormSession(urlSessionId: string | undefined, navigate: NavigateFunction) {
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
  const { chatWindow, entries: activityLog } = useChatWindow(sessionId)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // No session ID in URL → create a new empty session and redirect
  useEffect(() => {
    if (urlSessionId) return
    let cancelled = false
    ;(async () => {
      try {
        const session = await formClient.createSession()
        if (!cancelled) navigate(`/form/c/${session.session_id}`, { replace: true })
      } catch {
        // ignore — user can still upload a PDF and a session will be created then
      }
    })()
    return () => { cancelled = true }
  }, [urlSessionId, navigate])

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

        const [convData, ...rest] = await Promise.all([
          formClient.listConversations(ctx.session_id).catch(() => []),
          ...(ctx.document_id ? [
            formClient.getFields(ctx.document_id),
            formClient.getAnnotations(ctx.document_id).catch(() => [] as Annotation[]),
            formClient.getMap(ctx.document_id).catch(() => ({ document_id: ctx.document_id!, maps: [] as FieldLabelMap[] })),
          ] : []),
        ])
        if (cancelled) return

        chatWindow.load(convData.map((c: { id: string; role: string; content: string; created_at: string | null }) => ({
          id: c.id,
          role: c.role as "user" | "agent" | "system",
          text: c.content,
          timestamp: c.created_at ?? new Date().toISOString(),
        })))

        if (ctx.document_id && rest.length === 3) {
          const [fieldsData, annotationsData, mapsData] = rest as [
            { fields: FormField[]; text_blocks: TextBlock[]; page_count: number },
            Annotation[],
            { document_id: string; maps: FieldLabelMap[] },
          ]
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
          setAnnotations(annotationsData)
          setFieldLabelMaps(mapsData.maps)
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

      const [fieldsData, existingAnnotations, existingMaps] = await Promise.all([
        formClient.getFields(document_id),
        formClient.getAnnotations(document_id).catch(() => []),
        formClient.getMap(document_id).catch(() => ({ document_id, maps: [] })),
      ])
      setTextBlocks(fieldsData.text_blocks)
      setAnnotations(existingAnnotations)
      setFieldLabelMaps(existingMaps.maps)

      // Attach document to the existing session (created on /form entry)
      if (sessionId) {
        await formClient.updateSessionDocument(sessionId, document_id)
      } else {
        const session = await formClient.createSession(document_id)
        setSessionId(session.session_id)
        navigate(`/form/c/${session.session_id}`, { replace: true })
      }

      setMode("preview")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, navigate])

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

  return {
    // state
    documentId, sessionId, form, fields, textBlocks, annotations,
    mode, currentPage, selectedLabelId, selectedFieldId,
    isLoading, isFilling, isAsking, isMapping, isUnderstanding,
    rulesItems, fieldLabelMaps, pendingQuestions, askHistory,
    error, isDragging, excludedPages, activityLog,
    // setters (consumed by mode hooks)
    setFields, setAnnotations, setMode, setSelectedLabelId, setSelectedFieldId,
    setIsLoading, setIsFilling, setIsAsking, setIsMapping, setIsUnderstanding,
    setRulesItems, setFieldLabelMaps, setPendingQuestions, setAskHistory,
    setError, setIsDragging, setCurrentPage,
    // derived
    pageImageUrl: documentId ? formClient.getPagePreview(documentId, currentPage) : null,
    totalPages: form?.page_count ?? 1,
    // handlers
    fileInputRef, handleFileInput, handleDrop,
    handleUpload, handleToggleIncludePage, handleModeChange, handleValueChange,
    chatWindow,
  }
}
