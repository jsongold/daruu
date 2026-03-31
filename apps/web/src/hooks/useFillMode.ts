import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { AgentQuestion, FormField, Mode } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

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
  chatWindow: ChatWindow
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
  chatWindow,
}: Args) {
  const handleFill = useCallback(
    async (askAnswers?: Record<string, string>) => {
      if (!sessionId) return
      setIsFilling(true)
      setMode("fill")
      setError(null)

      if (askAnswers) {
        const summary = Object.entries(askAnswers)
          .map(([q, a]) => `${q}: ${a}`)
          .join("\n")
        setAskHistory((prev) => [...prev, { role: "user", content: summary }])
        chatWindow.add("user", summary)
      } else {
        chatWindow.add("system", "Fill started...")
      }

      try {
        const result = await formClient.fill(sessionId, askAnswers)

        if (result.fields.length > 0) {
          // Update fields from schema if available, otherwise patch from fields array
          if (result.schema) {
            setFields((prev) =>
              prev.map((f) => {
                const schemaField = result.schema!.fields.find((sf) => sf.field_id === f.id)
                return schemaField?.default_value != null
                  ? { ...f, value: schemaField.default_value }
                  : f
              })
            )
          } else {
            setFields((prev) =>
              prev.map((f) => {
                const filled = result.fields.find((item) => item.field_id === f.id)
                return filled ? { ...f, value: filled.value } : f
              })
            )
          }
          chatWindow.addBatch([
            ...result.fields.map((item) => ({
              role: "agent" as const,
              text: `Filled "${fields.find((f) => f.id === item.field_id)?.name ?? item.field_id}" = "${item.value}"`,
            })),
            { role: "system" as const, text: `Fill complete: ${result.fields.length} fields filled` },
          ])
        }

        if (result.ask.length > 0) {
          setPendingQuestions(result.ask)
          const combinedQuestion = result.ask.map((q) => q.question).join("\n")
          setAskHistory((prev) => [...prev, { role: "agent", content: combinedQuestion }])
          chatWindow.add("agent", combinedQuestion)
          setIsFilling(false)
          setMode("preview")
          return
        }

        setPendingQuestions([])
        setMode("preview")
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Fill failed"
        setError(msg)
        chatWindow.add("system", `Fill failed: ${msg}`)
        setMode("preview")
      } finally {
        setIsFilling(false)
      }
    },
    [sessionId, fields, setFields, setMode, setIsFilling, setAskHistory, setPendingQuestions, setError, chatWindow]
  )

  const handleAskReply = useCallback(
    (message: string) => {
      // Free-text reply: map each pending question to the user's message
      const answers: Record<string, string> = {}
      for (const q of pendingQuestions) {
        answers[q.question] = message
      }
      handleFill(answers)
    },
    [handleFill, pendingQuestions]
  )

  const handleModalSubmit = useCallback(
    (answers: Array<{ field_id: string | null; question: string; answer: string | null }>) => {
      setPendingQuestions([])
      const askAnswers: Record<string, string> = {}
      for (const a of answers) {
        if (a.answer !== null) {
          askAnswers[a.question] = a.answer
        }
      }
      if (Object.keys(askAnswers).length > 0) {
        handleFill(askAnswers)
      }
    },
    [handleFill, setPendingQuestions]
  )

  const handleModalClose = useCallback(() => {
    setPendingQuestions([])
  }, [setPendingQuestions])

  return { handleFill, handleAskReply, handleModalSubmit, handleModalClose }
}
