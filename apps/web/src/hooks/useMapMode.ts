import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { FieldLabelMap } from "../api/formClient"
import type { ActivityEntry } from "../components/InfoChat"

interface Args {
  documentId: string | null
  setFieldLabelMaps: React.Dispatch<React.SetStateAction<FieldLabelMap[]>>
  setIsMapping: (v: boolean) => void
  setError: (msg: string | null) => void
  addActivity: (role: ActivityEntry["role"], text: string) => void
}

export function useMapMode({
  documentId,
  setFieldLabelMaps,
  setIsMapping,
  setError,
  addActivity,
}: Args) {
  const handleRunMap = useCallback(async () => {
    if (!documentId) return
    setIsMapping(true)
    setError(null)
    try {
      const result = await formClient.runMap(documentId)
      setFieldLabelMaps(result.maps)
      addActivity(
        "system",
        `Map complete: ${result.maps.filter((m) => m.label_text).length}/${result.maps.length} fields identified`
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Map failed")
    } finally {
      setIsMapping(false)
    }
  }, [documentId, setFieldLabelMaps, setIsMapping, setError, addActivity])

  return { handleRunMap }
}
