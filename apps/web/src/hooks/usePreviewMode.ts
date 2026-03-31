import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { AgentQuestion, Mode } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  conversationId: string | null
  setIsAsking: (v: boolean) => void
  setMode: (mode: Mode) => void
  setPendingQuestions: React.Dispatch<React.SetStateAction<AgentQuestion[]>>
  setAskHistory: React.Dispatch<React.SetStateAction<Array<{ role: string; content: string }>>>
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function usePreviewMode({
  conversationId,
  setIsAsking,
  setMode,
  setPendingQuestions,
  setAskHistory,
  setError,
  chatWindow,
}: Args) {
  const handleSendInfo = useCallback(
    async (text: string) => {
      if (!conversationId) return
      chatWindow.add("user", text)
      await formClient.updateUserInfo(conversationId, { [`note_${Date.now()}`]: text })
    },
    [conversationId, chatWindow]
  )

  const handleAsk = useCallback(async () => {
    if (!conversationId) return
    setIsAsking(true)
    setMode("ask")
    setError(null)
    chatWindow.add("system", "Ask started...")
    try {
      const result = await formClient.ask(conversationId)
      if (result.questions.length > 0) {
        setPendingQuestions(result.questions)
        const combinedQuestion = result.questions.map((q) => q.question).join("\n")
        setAskHistory((prev) => [...prev, { role: "agent", content: combinedQuestion }])
        chatWindow.add("agent", combinedQuestion)
      } else {
        chatWindow.add("system", "No questions needed -- all fields have sufficient context.")
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ask failed"
      setError(msg)
      chatWindow.add("system", `Ask failed: ${msg}`)
    } finally {
      setIsAsking(false)
      setMode("preview")
    }
  }, [conversationId, setIsAsking, setMode, setPendingQuestions, setAskHistory, setError, chatWindow])

  return { handleSendInfo, handleAsk }
}
