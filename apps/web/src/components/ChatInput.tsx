import { useRef, useState } from "react"

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
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const isLoading = externalLoading || sending

  const submit = async () => {
    const text = input.trim()
    if (!text || disabled || isLoading) return
    setInput("")
    if (textareaRef.current) textareaRef.current.style.height = "auto"
    setSending(true)
    try {
      await onSend(text)
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await submit()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
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
      <textarea
        ref={textareaRef}
        rows={1}
        value={input}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={isLoading ? "Waiting..." : placeholder}
        disabled={disabled || isLoading}
        className={`${inputClass} resize-none overflow-y-auto`}
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
