import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { FieldLabelMap } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  documentId: string | null
  setFieldLabelMaps: React.Dispatch<React.SetStateAction<FieldLabelMap[]>>
  setIsMapping: (v: boolean) => void
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function useMapMode({
  documentId,
  setFieldLabelMaps,
  setIsMapping,
  setError,
  chatWindow,
}: Args) {
  const handleRunMap = useCallback(async () => {
    if (!documentId) return
    setIsMapping(true)
    setError(null)
    chatWindow.add("system", "Map started...")
    try {
      const result = await formClient.runMap(documentId)
      setFieldLabelMaps(result.maps)
      const identified = result.maps.filter((m) => m.label_text).length
      chatWindow.add("system", `Map complete: ${identified}/${result.maps.length} fields identified`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Map failed"
      setError(msg)
      chatWindow.add("system", `Map failed: ${msg}`)
    } finally {
      setIsMapping(false)
    }
  }, [documentId, setFieldLabelMaps, setIsMapping, setError, chatWindow])

  return { handleRunMap }
}
