import { useCallback } from "react"
import { formClient } from "../api/formClient"
import type { FormField } from "../api/formClient"
import type { ChatWindow } from "../lib/ChatWindow"

interface Args {
  conversationId: string | null
  setFields: React.Dispatch<React.SetStateAction<FormField[]>>
  setError: (msg: string | null) => void
  chatWindow: ChatWindow
}

export function useFieldCorrection({
  conversationId,
  setFields,
  setError,
  chatWindow,
}: Args) {
  const handleEditField = useCallback(
    async (field: FormField, newValue: string) => {
      if (!conversationId) return
      setError(null)
      const oldValue = field.value ?? ""
      try {
        await formClient.updateFieldValue(conversationId, field.id, newValue, field.name)
        setFields((prev) =>
          prev.map((f) => (f.id === field.id ? { ...f, value: newValue } : f))
        )
        chatWindow.add(
          "system",
          `Corrected "${field.name}": "${oldValue}" → "${newValue}"`
        )
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to update field"
        setError(msg)
        chatWindow.add("system", `Field update failed: ${msg}`)
      }
    },
    [conversationId, setFields, setError, chatWindow]
  )

  const handleDeleteField = useCallback(
    async (field: FormField) => {
      if (!conversationId) return
      setError(null)
      const oldValue = field.value ?? ""
      try {
        await formClient.deleteFieldValue(conversationId, field.id, field.name)
        setFields((prev) =>
          prev.map((f) => (f.id === field.id ? { ...f, value: null } : f))
        )
        chatWindow.add("system", `Deleted "${field.name}": "${oldValue}" removed`)
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Failed to delete field value"
        setError(msg)
        chatWindow.add("system", `Field delete failed: ${msg}`)
      }
    },
    [conversationId, setFields, setError, chatWindow]
  )

  return { handleEditField, handleDeleteField }
}
