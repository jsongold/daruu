import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { Mode } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  conversationId: string | null
  setRulesItems: React.Dispatch<React.SetStateAction<string[]>>
  setMode: (mode: Mode) => void
  setIsUnderstanding: (v: boolean) => void
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function useRulesMode({
  conversationId,
  setRulesItems,
  setMode,
  setIsUnderstanding,
  setError,
  chatWindow,
}: Args) {
  const handleUnderstand = useCallback(async () => {
    if (!conversationId) return
    setIsUnderstanding(true)
    setError(null)
    chatWindow.add("system", "Understand started...")
    try {
      const ctx = await formClient.understand(conversationId)
      const count = ctx.rules?.items?.length ?? 0
      setRulesItems((ctx.rules?.items ?? []).map((r: any) => typeof r === "string" ? r : r.rule_text ?? ""))
      chatWindow.add("system", `Understand complete: ${count} rules extracted`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Understand failed"
      setError(msg)
      chatWindow.add("system", `Understand failed: ${msg}`)
    } finally {
      setIsUnderstanding(false)
    }
  }, [conversationId, setRulesItems, setMode, setIsUnderstanding, setError, chatWindow])

  const handleSaveRules = useCallback(
    async (items: string[]) => {
      if (!conversationId) return
      try {
        const ctx = await formClient.updateRules(conversationId, items)
        setRulesItems((ctx.rules?.items ?? []).map((r: any) => typeof r === "string" ? r : r.rule_text ?? ""))
        chatWindow.add("system", `Rules saved: ${items.length} rules`)
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to save rules"
        setError(msg)
        chatWindow.add("system", `Rules save failed: ${msg}`)
      }
    },
    [conversationId, setRulesItems, setError, chatWindow]
  )

  return { handleUnderstand, handleSaveRules }
}
