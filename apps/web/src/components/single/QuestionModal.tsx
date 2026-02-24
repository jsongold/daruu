/**
 * QuestionModal — Claude-style bottom-center floating modal for detailed autofill Q&A.
 *
 * Displays a single question at a time. User answers by selecting an option
 * or typing free text. Has a "Just Fill" bail-out button on every question.
 */

import { useState } from 'react';
import type { QuestionOption } from '../../api/autofillPipelineClient';

interface QuestionModalProps {
  question: string;
  questionType: 'single_choice' | 'multiple_choice' | 'free_text' | 'confirm';
  options: QuestionOption[];
  context?: string | null;
  onSubmit: (answer: { selectedOptionIds: string[]; freeText?: string }) => void;
  onJustFill: () => void;
  isSubmitting?: boolean;
}

export function QuestionModal({
  question,
  questionType,
  options,
  context,
  onSubmit,
  onJustFill,
  isSubmitting = false,
}: QuestionModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [freeText, setFreeText] = useState('');

  const handleOptionToggle = (id: string) => {
    if (questionType === 'single_choice' || questionType === 'confirm') {
      setSelectedIds([id]);
    } else {
      setSelectedIds(prev =>
        prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
      );
    }
  };

  const handleSubmit = () => {
    if (questionType === 'free_text') {
      onSubmit({ selectedOptionIds: [], freeText: freeText.trim() });
    } else {
      onSubmit({ selectedOptionIds: selectedIds });
    }
  };

  const canSubmit =
    questionType === 'free_text'
      ? freeText.trim().length > 0
      : selectedIds.length > 0;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex justify-center pb-6 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-xl mx-4 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden">
        {/* Question */}
        <div className="p-5">
          <p className="text-sm font-medium text-gray-900 leading-relaxed">
            {question}
          </p>
        </div>

        {/* Options */}
        {(questionType === 'single_choice' || questionType === 'confirm') && options.length > 0 && (
          <div className="px-5 pb-3 space-y-2">
            {options.map(opt => (
              <label
                key={opt.id}
                className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                  selectedIds.includes(opt.id)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <input
                  type="radio"
                  name="question-option"
                  checked={selectedIds.includes(opt.id)}
                  onChange={() => handleOptionToggle(opt.id)}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">{opt.label}</span>
              </label>
            ))}
          </div>
        )}

        {questionType === 'multiple_choice' && options.length > 0 && (
          <div className="px-5 pb-3 space-y-2">
            {options.map(opt => (
              <label
                key={opt.id}
                className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                  selectedIds.includes(opt.id)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.includes(opt.id)}
                  onChange={() => handleOptionToggle(opt.id)}
                  className="text-blue-600 focus:ring-blue-500 rounded"
                />
                <span className="text-sm text-gray-700">{opt.label}</span>
              </label>
            ))}
          </div>
        )}

        {questionType === 'free_text' && (
          <div className="px-5 pb-3">
            <textarea
              value={freeText}
              onChange={e => setFreeText(e.target.value)}
              placeholder="Type your answer..."
              rows={3}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>
        )}

        {/* Context */}
        {context && (
          <div className="px-5 pb-3">
            <p className="text-xs text-gray-400 leading-relaxed">{context}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between px-5 py-3 bg-gray-50 border-t border-gray-100">
          <button
            onClick={onJustFill}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          >
            Just Fill
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Processing...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}
