import { useEffect, useRef, useState } from "react"
import { ChatWindow } from "../lib/ChatWindow"
import type { ActivityEntry } from "../lib/ChatWindow"
import { formClient } from "../api/formClient"

export function useChatWindow(sessionId: string | null): {
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

      // Persist only entries added after load() — those beyond persistedCount
      if (sessionId && current.length > persistedCount.current) {
        const latest = current[current.length - 1]
        if (latest) {
          formClient.addConversation(sessionId, latest.role, latest.text).catch(() => {})
        }
      }
    })
  }, [chatWindow, sessionId])

  // Wrap load once so we can track how many entries came from the DB
  useEffect(() => {
    const originalLoad = chatWindow.load.bind(chatWindow)
    chatWindow.load = (loaded: ActivityEntry[]) => {
      originalLoad(loaded)
      persistedCount.current = loaded.length
    }
  }, [chatWindow])

  return { chatWindow, entries }
}
