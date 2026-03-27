import { useRef, useEffect } from "react"
import type { Mode } from "../api/formClient"
import { ChatBubble } from "./ChatBubble"
import { ChatInput } from "./ChatInput"

interface Message {
  role: string
  content: string
}

interface Props {
  history: Message[]
  onReply: (message: string) => void
  mode: Mode
  isLoading: boolean
}

export function AskPanel({ history, onReply, mode, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [history])

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-gray-200">
        <h2 className="font-semibold text-gray-800 text-sm">
          {mode === "fill" ? "Filling..." : "Ask Agent"}
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {mode === "fill" ? "Agent is filling the form" : "Conversation with the agent"}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {history.length === 0 && !isLoading && (
          <p className="text-xs text-gray-400 text-center mt-8">No messages yet</p>
        )}
        {history.map((msg, i) => (
          <ChatBubble
            key={i}
            role={msg.role === "user" ? "user" : "agent"}
            text={msg.content}
          />
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-500 px-3 py-2 rounded-lg rounded-tl-sm text-xs flex items-center gap-1">
              <span className="inline-block w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              {mode === "fill" ? "Filling form..." : "Agent is thinking..."}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {(mode === "ask" || mode === "fill") && (
        <ChatInput
          onSend={onReply}
          isLoading={isLoading}
          placeholder="Type your reply..."
          rounded="full"
        />
      )}
    </div>
  )
}
