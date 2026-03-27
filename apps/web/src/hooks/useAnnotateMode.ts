import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { FormField, TextBlock, Annotation, Mode } from "../api/formClient"

interface Args {
  mode: Mode
  selectedLabelId: string | null
  documentId: string | null
  textBlocks: TextBlock[]
  setAnnotations: React.Dispatch<React.SetStateAction<Annotation[]>>
  setSelectedLabelId: (id: string | null) => void
  setSelectedFieldId: (id: string | null) => void
  setIsLoading: (v: boolean) => void
  setError: (msg: string | null) => void
}

export function useAnnotateMode({
  mode,
  selectedLabelId,
  documentId,
  textBlocks,
  setAnnotations,
  setSelectedLabelId,
  setSelectedFieldId,
  setIsLoading,
  setError,
}: Args) {
  const handleLabelClick = useCallback(
    (block: TextBlock) => {
      if (mode !== "annotate") return
      setSelectedLabelId(block.id)
      setSelectedFieldId(null)
    },
    [mode, setSelectedLabelId, setSelectedFieldId]
  )

  const handleFieldClick = useCallback(
    async (field: FormField) => {
      if (mode !== "annotate") return
      if (!selectedLabelId || !documentId) return

      const labelBlock = textBlocks.find((b) => b.id === selectedLabelId)
      if (!labelBlock) return

      setIsLoading(true)
      setError(null)
      try {
        const annotation = await formClient.createAnnotation({
          document_id: documentId,
          label_text: labelBlock.text,
          label_bbox: labelBlock.bbox,
          label_page: labelBlock.page,
          field_id: field.id,
          field_name: field.name,
          field_bbox: field.bbox ?? undefined,
          field_page: field.page,
        })
        setAnnotations((prev) => [...prev, annotation])
        setSelectedLabelId(null)
        setSelectedFieldId(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create annotation")
      } finally {
        setIsLoading(false)
      }
    },
    [mode, selectedLabelId, documentId, textBlocks, setAnnotations, setSelectedLabelId, setSelectedFieldId, setIsLoading, setError]
  )

  const handleDeleteAnnotation = useCallback(
    async (id: string) => {
      setError(null)
      try {
        await formClient.deleteAnnotation(id)
        setAnnotations((prev) => prev.filter((a) => a.id !== id))
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete annotation")
      }
    },
    [setAnnotations, setError]
  )

  return { handleLabelClick, handleFieldClick, handleDeleteAnnotation }
}
