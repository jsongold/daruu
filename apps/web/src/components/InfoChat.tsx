import { useRef, useEffect } from "react"
import { ChatBubble } from "./ChatBubble"
import { ChatInput } from "./ChatInput"
export type { ActivityRole, ActivityEntry } from "../lib/ChatWindow"

import type { ActivityEntry } from "../lib/ChatWindow"

interface Props {
  entries: ActivityEntry[]
  onSend: (text: string) => Promise<void>
  disabled?: boolean
}

export function ActivityLog({ entries, onSend, disabled }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [entries])

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-gray-200">
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Context
        </h2>
        <p className="text-[11px] text-gray-400 mt-0.5">
          Activity log -- agent, user, and system
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
        {entries.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-6">
            e.g. "My name is Taro, I work at Acme Corp"
          </p>
        )}
        {entries.map((entry) => (
          <ChatBubble key={entry.id} role={entry.role} text={entry.text} />
        ))}
        <div ref={bottomRef} />
      </div>

      <ChatInput
        onSend={onSend}
        disabled={disabled}
        placeholder="Type info and press Enter..."
      />
    </div>
  )
}
