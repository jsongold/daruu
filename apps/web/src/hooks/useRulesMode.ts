import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { Mode } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  sessionId: string | null
  setRulesItems: React.Dispatch<React.SetStateAction<string[]>>
  setMode: (mode: Mode) => void
  setIsUnderstanding: (v: boolean) => void
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function useRulesMode({
  sessionId,
  setRulesItems,
  setMode,
  setIsUnderstanding,
  setError,
  chatWindow,
}: Args) {
  const handleUnderstand = useCallback(async () => {
    if (!sessionId) return
    setIsUnderstanding(true)
    setError(null)
    chatWindow.add("system", "Understand started...")
    try {
      const ctx = await formClient.understand(sessionId)
      const count = ctx.rules?.items?.length ?? 0
      setRulesItems(ctx.rules?.items ?? [])
      setMode("rules")
      chatWindow.add("system", `Understand complete: ${count} rules extracted`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Understand failed"
      setError(msg)
      chatWindow.add("system", `Understand failed: ${msg}`)
    } finally {
      setIsUnderstanding(false)
    }
  }, [sessionId, setRulesItems, setMode, setIsUnderstanding, setError, chatWindow])

  const handleSaveRules = useCallback(
    async (items: string[]) => {
      if (!sessionId) return
      try {
        const ctx = await formClient.updateRules(sessionId, items)
        setRulesItems(ctx.rules?.items ?? [])
        chatWindow.add("system", `Rules saved: ${items.length} rules`)
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to save rules"
        setError(msg)
        chatWindow.add("system", `Rules save failed: ${msg}`)
      }
    },
    [sessionId, setRulesItems, setError, chatWindow]
  )

  return { handleUnderstand, handleSaveRules }
}
