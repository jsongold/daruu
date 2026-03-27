import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { Mode } from "../api/formClient"

interface Args {
  sessionId: string | null
  setRulesItems: React.Dispatch<React.SetStateAction<string[]>>
  setMode: (mode: Mode) => void
  setIsUnderstanding: (v: boolean) => void
  setError: (msg: string | null) => void
}

export function useRulesMode({
  sessionId,
  setRulesItems,
  setMode,
  setIsUnderstanding,
  setError,
}: Args) {
  const handleUnderstand = useCallback(async () => {
    if (!sessionId) return
    setIsUnderstanding(true)
    setError(null)
    try {
      const ctx = await formClient.understand(sessionId)
      setRulesItems(ctx.rules?.items ?? [])
      setMode("rules")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Understand failed")
    } finally {
      setIsUnderstanding(false)
    }
  }, [sessionId, setRulesItems, setMode, setIsUnderstanding, setError])

  const handleSaveRules = useCallback(
    async (items: string[]) => {
      if (!sessionId) return
      try {
        const ctx = await formClient.updateRules(sessionId, items)
        setRulesItems(ctx.rules?.items ?? [])
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save rules")
      }
    },
    [sessionId, setRulesItems, setError]
  )

  return { handleUnderstand, handleSaveRules }
}
