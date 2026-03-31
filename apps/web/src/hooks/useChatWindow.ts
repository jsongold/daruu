import { useEffect, useRef, useState } from "react"
import { ChatWindow } from "../lib/ChatWindow"
import type { ActivityEntry } from "../lib/ChatWindow"
import { formClient } from "../api/formClient"

export function useChatWindow(conversationId: string | null): {
  chatWindow: ChatWindow
  entries: ActivityEntry[]
} {
  const chatWindow = useRef(new ChatWindow()).current
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const persistedCount = useRef(0)

  useEffect(() => {
    return chatWindow.subscribe(() => {
      const current = [...chatWindow.entries]
      setEntries(current)

      // Persist only entries added after load() -- those beyond persistedCount
      if (conversationId && current.length > persistedCount.current) {
        const newEntries = current.slice(persistedCount.current)
        persistedCount.current = current.length
        for (const entry of newEntries) {
          formClient.addMessage(conversationId, entry.role, entry.text).catch(() => {})
        }
      }
    })
  }, [chatWindow, conversationId])

  // Wrap load once so we can track how many entries came from the DB
  useEffect(() => {
    const originalLoad = chatWindow.load.bind(chatWindow)
    chatWindow.load = (loaded: ActivityEntry[]) => {
      persistedCount.current = loaded.length
      originalLoad(loaded)
    }
  }, [chatWindow])

  return { chatWindow, entries }
}
