import { useState, useCallback, useRef, useEffect } from "react"
import type { NavigateFunction } from "react-router-dom"
import { formClient } from "../api/formClient"
import type { Form, FormField, TextBlock, Annotation, Mode, AgentQuestion, FieldLabelMap } from "../api/formClient"
import { useChatWindow } from "./useChatWindow"

export function useFormSession(urlConversationId: string | undefined, navigate: NavigateFunction) {
  const [formId, setFormId] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [fields, setFields] = useState<FormField[]>([])
  const [textBlocks, setTextBlocks] = useState<TextBlock[]>([])
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [mode, setMode] = useState<Mode>("edit")
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
  const { chatWindow, entries: activityLog } = useChatWindow(conversationId)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // No conversation ID in URL -> create a new empty conversation and redirect
  useEffect(() => {
    if (urlConversationId) return
    let cancelled = false
    ;(async () => {
      try {
        const conv = await formClient.createConversation()
        if (!cancelled) navigate(`/form/c/${conv.conversation_id}`, { replace: true })
      } catch {
        // ignore -- user can still upload a PDF and a conversation will be created then
      }
    })()
    return () => { cancelled = true }
  }, [urlConversationId, navigate])

  // Restore conversation from URL
  useEffect(() => {
    if (!urlConversationId) return
    let cancelled = false
    setIsLoading(true)
    setError(null)

    ;(async () => {
      try {
        const ctx = await formClient.getConversation(urlConversationId)
        if (cancelled) return
        setConversationId(ctx.conversation_id)
        setFormId(ctx.form_id)
        if (ctx.form) {
          setForm(ctx.form)
          const formValues = ctx.form_values ?? {}
          setFields(
            ctx.form.fields.map((f) =>
              formValues[f.id] !== undefined ? { ...f, value: formValues[f.id] } : f
            )
          )
        }
        setAnnotations(ctx.annotations)
        setRulesItems((ctx.rules?.items ?? []).map((r: any) => typeof r === "string" ? r : r.rule_text ?? ""))
        const restoredMode = ctx.mode as Mode
        const UI_MODES: Mode[] = ["edit", "annotate"]
        setMode(UI_MODES.includes(restoredMode) ? restoredMode : "edit")

        const [msgData, ...rest] = await Promise.all([
          formClient.listMessages(ctx.conversation_id).catch(() => []),
          ...(ctx.form_id ? [
            formClient.getFields(ctx.form_id),
            formClient.getAnnotations(ctx.form_id).catch(() => [] as Annotation[]),
            formClient.getMap(ctx.form_id).catch(() => ({ form_id: ctx.form_id!, maps: [] as FieldLabelMap[] })),
          ] : []),
        ])
        if (cancelled) return

        chatWindow.load(msgData.map((c: { id: string; role: string; content: string; created_at: string | null }) => ({
          id: c.id,
          role: c.role as "user" | "agent" | "system",
          text: c.content,
          timestamp: c.created_at ?? new Date().toISOString(),
        })))

        if (ctx.form_id && rest.length === 3) {
          const [fieldsData, annotationsData, mapsData] = rest as [
            { fields: FormField[]; text_blocks: TextBlock[]; page_count: number },
            Annotation[],
            { form_id: string; maps: FieldLabelMap[] },
          ]
          setTextBlocks(fieldsData.text_blocks)
          if (!ctx.form && fieldsData.fields.length > 0) {
            const formValues = ctx.form_values ?? {}
            const withValues = fieldsData.fields.map((f) =>
              formValues[f.id] !== undefined ? { ...f, value: formValues[f.id] } : f
            )
            setFields(withValues)
            setForm({
              id: ctx.form_id,
              form_id: ctx.form_id,
              fields: fieldsData.fields,
              page_count: fieldsData.page_count ?? 1,
            })
          }
          setAnnotations(annotationsData)
          setFieldLabelMaps(mapsData.maps)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load conversation")
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    })()

    return () => { cancelled = true }
  }, [urlConversationId])

  const handleUpload = useCallback(async (file: File) => {
    if (!file.name.endsWith(".pdf")) {
      setError("Please upload a PDF file")
      return
    }
    setIsLoading(true)
    setError(null)
    setExcludedPages(new Set())
    try {
      const { form_id, form: uploadedForm } = await formClient.uploadForm(file)
      setFormId(form_id)
      setForm(uploadedForm)
      setFields(uploadedForm.fields)
      setCurrentPage(1)

      const [fieldsData, existingAnnotations, existingMaps] = await Promise.all([
        formClient.getFields(form_id),
        formClient.getAnnotations(form_id).catch(() => []),
        formClient.getMap(form_id).catch(() => ({ form_id, maps: [] })),
      ])
      setTextBlocks(fieldsData.text_blocks)
      setAnnotations(existingAnnotations)
      setFieldLabelMaps(existingMaps.maps)

      // Attach form to the existing conversation (created on /form entry)
      if (conversationId) {
        await formClient.updateConversationForm(conversationId, form_id)
      } else {
        const conv = await formClient.createConversation(form_id)
        setConversationId(conv.conversation_id)
        navigate(`/form/c/${conv.conversation_id}`, { replace: true })
      }

      setMode("edit")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setIsLoading(false)
    }
  }, [conversationId, navigate])

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
    formId, conversationId, form, fields, textBlocks, annotations,
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
    pageImageUrl: formId ? formClient.getPagePreview(formId, currentPage) : null,
    totalPages: form?.page_count ?? 1,
    // handlers
    fileInputRef, handleFileInput, handleDrop,
    handleUpload, handleToggleIncludePage, handleModeChange, handleValueChange,
    chatWindow,
  }
}
