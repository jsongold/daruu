export type ChatRole = "user" | "agent" | "system"

interface Props {
  role: ChatRole
  text: string
}

export function ChatBubble({ role, text }: Props) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white text-xs rounded-lg rounded-tr-sm px-3 py-1.5 max-w-[90%] break-words">
          {text}
        </div>
      </div>
    )
  }

  if (role === "agent") {
    return (
      <div className="flex justify-start">
        <div className="bg-gray-100 text-gray-800 text-xs rounded-lg rounded-tl-sm px-3 py-1.5 max-w-[90%] break-words">
          {text}
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-center">
      <span className="text-gray-400 italic text-[11px]">{text}</span>
    </div>
  )
}
