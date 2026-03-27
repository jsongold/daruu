import { useState } from "react"

interface Props {
  onSend: (text: string) => void | Promise<void>
  disabled?: boolean
  placeholder?: string
  isLoading?: boolean
  rounded?: "full" | "default"
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Type and press Enter...",
  isLoading: externalLoading = false,
  rounded = "default",
}: Props) {
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)

  const isLoading = externalLoading || sending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || disabled || isLoading) return
    setInput("")
    setSending(true)
    try {
      await onSend(text)
    } finally {
      setSending(false)
    }
  }

  const inputClass = [
    "flex-1 text-xs border border-gray-300 px-2 py-1.5 focus:outline-none focus:border-blue-400 disabled:opacity-50",
    rounded === "full" ? "rounded-full focus:ring-1 focus:ring-blue-100" : "rounded",
  ].join(" ")

  const btnClass = [
    "px-3 py-1.5 text-xs bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed",
    rounded === "full" ? "rounded-full" : "rounded",
  ].join(" ")

  return (
    <form onSubmit={handleSubmit} className="p-2 border-t border-gray-200 flex gap-2">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={isLoading ? "Waiting..." : placeholder}
        disabled={disabled || isLoading}
        className={inputClass}
      />
      <button
        type="submit"
        disabled={!input.trim() || disabled || isLoading}
        className={btnClass}
      >
        {isLoading ? "..." : "Send"}
      </button>
    </form>
  )
}
