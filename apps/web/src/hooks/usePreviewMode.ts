import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { AgentQuestion, Mode } from "../api/formClient"
import type { ActivityEntry } from "../components/InfoChat"

interface Args {
  sessionId: string | null
  setIsAsking: (v: boolean) => void
  setMode: (mode: Mode) => void
  setPendingQuestions: React.Dispatch<React.SetStateAction<AgentQuestion[]>>
  setAskHistory: React.Dispatch<React.SetStateAction<Array<{ role: string; content: string }>>>
  setError: (msg: string | null) => void
  addActivity: (role: ActivityEntry["role"], text: string) => void
}

export function usePreviewMode({
  sessionId,
  setIsAsking,
  setMode,
  setPendingQuestions,
  setAskHistory,
  setError,
  addActivity,
}: Args) {
  const handleSendInfo = useCallback(
    async (text: string) => {
      if (!sessionId) return
      addActivity("user", text)
      await formClient.updateUserInfo(sessionId, { note: text })
    },
    [sessionId, addActivity]
  )

  const handleAsk = useCallback(async () => {
    if (!sessionId) return
    setIsAsking(true)
    setMode("ask")
    setError(null)
    try {
      const result = await formClient.ask(sessionId)
      if (result.questions.length > 0) {
        setPendingQuestions(result.questions)
        const combinedQuestion = result.questions.map((q) => q.question).join("\n")
        setAskHistory((prev) => [...prev, { role: "agent", content: combinedQuestion }])
        addActivity("agent", combinedQuestion)
      } else {
        addActivity("system", "No questions needed -- all fields have sufficient context.")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ask failed")
    } finally {
      setIsAsking(false)
      setMode("preview")
    }
  }, [sessionId, setIsAsking, setMode, setPendingQuestions, setAskHistory, setError, addActivity])

  return { handleSendInfo, handleAsk }
}
