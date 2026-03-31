import { useState } from "react"
import type { AgentQuestion } from "../api/formClient"

interface Answer {
  field_id: string | null
  question: string
  answer: string | null
}

interface Props {
  questions: AgentQuestion[]
  onSubmit: (answers: Answer[]) => void
  onClose: () => void
}

export function AskQuestionModal({ questions, onSubmit, onClose }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string | null>>({})
  const [otherText, setOtherText] = useState("")
  const [showOtherInput, setShowOtherInput] = useState(false)

  const question = questions[currentIndex]
  const total = questions.length
  const answered = answers[currentIndex]

  const goTo = (index: number) => {
    setCurrentIndex(index)
    setOtherText("")
    setShowOtherInput(false)
  }

  const selectOption = (option: string) => {
    setAnswers((prev) => ({ ...prev, [currentIndex]: option }))
    setShowOtherInput(false)
    setOtherText("")
    // Auto-advance to next unanswered question
    const next = findNextUnanswered(currentIndex, { ...answers, [currentIndex]: option })
    if (next !== null) setTimeout(() => goTo(next), 150)
  }

  const selectOther = () => {
    setShowOtherInput(true)
  }

  const submitOther = () => {
    const text = otherText.trim()
    if (!text) return
    setAnswers((prev) => ({ ...prev, [currentIndex]: text }))
    setShowOtherInput(false)
    setOtherText("")
    const next = findNextUnanswered(currentIndex, { ...answers, [currentIndex]: text })
    if (next !== null) setTimeout(() => goTo(next), 150)
  }

  const skipCurrent = () => {
    setAnswers((prev) => ({ ...prev, [currentIndex]: null }))
    setShowOtherInput(false)
    setOtherText("")
    const next = findNextUnanswered(currentIndex, { ...answers, [currentIndex]: null })
    if (next !== null) goTo(next)
  }

  const findNextUnanswered = (from: number, currentAnswers: Record<number, string | null>): number | null => {
    for (let i = from + 1; i < questions.length; i++) {
      if (!(i in currentAnswers)) return i
    }
    return null
  }

  const allAnswered = questions.every((_, i) => i in answers)

  const handleSubmit = () => {
    const result: Answer[] = questions.map((q, i) => ({
      field_id: q.field_id,
      question: q.question,
      answer: answers[i] ?? null,
    }))
    onSubmit(result)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center pb-6 px-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-lg bg-[#1c1c1e] rounded-2xl overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-start justify-between gap-3">
            <p className="text-white text-sm leading-snug flex-1">{question.question}</p>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => goTo(Math.max(0, currentIndex - 1))}
                disabled={currentIndex === 0}
                className="text-gray-400 hover:text-white disabled:opacity-20 transition-colors p-1"
              >
                ‹
              </button>
              <span className="text-gray-400 text-xs whitespace-nowrap">
                {total}件中{currentIndex + 1}件目
              </span>
              <button
                onClick={() => goTo(Math.min(total - 1, currentIndex + 1))}
                disabled={currentIndex === total - 1}
                className="text-gray-400 hover:text-white disabled:opacity-20 transition-colors p-1"
              >
                ›
              </button>
              <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-1 ml-1">
                ✕
              </button>
            </div>
          </div>
        </div>

        {/* Options */}
        <div className="divide-y divide-white/5">
          {question.options.map((option, i) => {
            const isSelected = answered === option
            return (
              <button
                key={i}
                onClick={() => selectOption(option)}
                className={[
                  "w-full flex items-center gap-4 px-5 py-3.5 text-left transition-colors",
                  isSelected
                    ? "bg-blue-600/20"
                    : "hover:bg-white/5 active:bg-white/10",
                ].join(" ")}
              >
                <span className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center text-xs text-gray-300 shrink-0 font-medium">
                  {i + 1}
                </span>
                <span className="flex-1 text-sm text-white">{option}</span>
                <span className="text-gray-500 text-xs">
                  {isSelected ? "✓" : "→"}
                </span>
              </button>
            )
          })}

          {/* Other option */}
          {showOtherInput ? (
            <div className="flex items-center gap-3 px-5 py-3">
              <span className="text-gray-400 shrink-0">✏</span>
              <input
                type="text"
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submitOther() }}
                placeholder="自由入力..."
                autoFocus
                className="flex-1 bg-transparent text-white text-sm outline-none placeholder-gray-500"
              />
              <button
                onClick={submitOther}
                disabled={!otherText.trim()}
                className="text-blue-400 text-sm disabled:opacity-30"
              >
                確定
              </button>
            </div>
          ) : (
            <button
              onClick={selectOther}
              className="w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-white/5 transition-colors"
            >
              <span className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center text-xs text-gray-300 shrink-0">
                ✏
              </span>
              <span className="flex-1 text-sm text-gray-400">その他</span>
              <button
                onClick={(e) => { e.stopPropagation(); skipCurrent() }}
                className="text-xs text-gray-400 border border-gray-600 rounded px-2 py-0.5 hover:border-gray-400 transition-colors"
              >
                スキップ
              </button>
            </button>
          )}
        </div>

        {/* Footer: submit when all answered */}
        {allAnswered && (
          <div className="px-5 py-3 border-t border-white/5">
            <button
              onClick={handleSubmit}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-xl transition-colors font-medium"
            >
              回答を送信
            </button>
          </div>
        )}

        {/* Progress dots */}
        {total > 1 && (
          <div className="flex justify-center gap-1.5 pb-4 pt-2">
            {questions.map((_, i) => (
              <button
                key={i}
                onClick={() => goTo(i)}
                className={[
                  "w-1.5 h-1.5 rounded-full transition-colors",
                  i === currentIndex
                    ? "bg-white"
                    : i in answers
                    ? "bg-blue-500"
                    : "bg-white/20",
                ].join(" ")}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
