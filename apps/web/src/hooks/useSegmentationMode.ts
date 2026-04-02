import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { Segment } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  formId: string | null
  setSegments: React.Dispatch<React.SetStateAction<Segment[]>>
  setIsSegmenting: (v: boolean) => void
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function useSegmentationMode({
  formId,
  setSegments,
  setIsSegmenting,
  setError,
  chatWindow,
}: Args) {
  const handleRunSegmentation = useCallback(async () => {
    if (!formId) return
    setIsSegmenting(true)
    setError(null)
    chatWindow.add("system", "Segmentation started...")
    try {
      // 1. Build grid-cell segments and save to DB
      const saved = await formClient.runSegmentation(formId, "fitz", "segments")
      // 2. Get raw lines for UI visualisation
      const lines = await formClient.runSegmentation(formId, "fitz", "lines")
      setSegments(lines.segments)
      chatWindow.add("system", `Segmentation complete: ${saved.segments.length} grid segments saved, ${lines.segments.length} lines displayed`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Segmentation failed"
      setError(msg)
      chatWindow.add("system", `Segmentation failed: ${msg}`)
    } finally {
      setIsSegmenting(false)
    }
  }, [formId, setSegments, setIsSegmenting, setError, chatWindow])

  return { handleRunSegmentation }
}
