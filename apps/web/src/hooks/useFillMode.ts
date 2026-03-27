import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { AgentQuestion, FormField, Mode } from "../api/formClient"
import type { ActivityEntry } from "../components/InfoChat"

interface Args {
  sessionId: string | null
  fields: FormField[]
  pendingQuestions: AgentQuestion[]
  setFields: React.Dispatch<React.SetStateAction<FormField[]>>
  setMode: (mode: Mode) => void
  setIsFilling: (v: boolean) => void
  setAskHistory: React.Dispatch<React.SetStateAction<Array<{ role: string; content: string }>>>
  setPendingQuestions: React.Dispatch<React.SetStateAction<AgentQuestion[]>>
  setError: (msg: string | null) => void
  addActivity: (role: ActivityEntry["role"], text: string) => void
}

export function useFillMode({
  sessionId,
  fields,
  pendingQuestions,
  setFields,
  setMode,
  setIsFilling,
  setAskHistory,
  setPendingQuestions,
  setError,
  addActivity,
}: Args) {
  const handleFill = useCallback(
    async (userMessage?: string) => {
      if (!sessionId) return
      setIsFilling(true)
      setMode("fill")
      setError(null)

      if (userMessage) {
        setAskHistory((prev) => [...prev, { role: "user", content: userMessage }])
        addActivity("user", userMessage)
      }

      try {
        const result = await formClient.fill(sessionId, userMessage)

        if (result.fields.length > 0) {
          setFields((prev) =>
            prev.map((f) => {
              const filled = result.fields.find((item) => item.field_id === f.id)
              return filled ? { ...f, value: filled.value } : f
            })
          )
          for (const item of result.fields) {
            const fieldName = fields.find((f) => f.id === item.field_id)?.name ?? item.field_id
            addActivity("system", `Filled "${fieldName}" = "${item.value}"`)
          }
        }

        if (result.ask.length > 0) {
          setPendingQuestions(result.ask)
          const combinedQuestion = result.ask.map((q) => q.question).join("\n")
          setAskHistory((prev) => [...prev, { role: "agent", content: combinedQuestion }])
          addActivity("agent", combinedQuestion)
          setIsFilling(false)
          setMode("preview")
          return
        }

        setPendingQuestions([])
        setMode("preview")
      } catch (err) {
        setError(err instanceof Error ? err.message : "Fill failed")
        setMode("preview")
      } finally {
        setIsFilling(false)
      }
    },
    [sessionId, fields, setFields, setMode, setIsFilling, setAskHistory, setPendingQuestions, setError, addActivity]
  )

  const handleAskReply = useCallback(
    (message: string) => {
      handleFill(message)
    },
    [handleFill]
  )

  const handleModalSubmit = useCallback(
    (answers: Array<{ field_id: string; answer: string | null }>) => {
      setPendingQuestions([])
      const parts = answers
        .filter((a) => a.answer !== null)
        .map((a) => {
          const q = pendingQuestions.find((q) => q.field_id === a.field_id)
          return q ? `${q.question}: ${a.answer}` : a.answer
        })
      const userMessage = parts.join("\n")
      if (userMessage) {
        handleFill(userMessage)
      }
    },
    [pendingQuestions, handleFill, setPendingQuestions]
  )

  const handleModalClose = useCallback(() => {
    setPendingQuestions([])
  }, [setPendingQuestions])

  return { handleFill, handleAskReply, handleModalSubmit, handleModalClose }
}
