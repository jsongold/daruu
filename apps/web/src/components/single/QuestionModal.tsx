/**
 * QuestionModal — Claude-style bottom-center floating modal for detailed autofill Q&A.
 *
 * Displays all questions at once in a scrollable list. User answers each question
 * with its own input (radio/checkbox/textarea). Has a "Just Fill" bail-out button.
 */

import { useState } from 'react';
import type { QuestionItem, QuestionOption } from '../../api/autofillPipelineClient';

interface QuestionAnswer {
  selectedOptionIds: string[];
  freeText?: string;
}

interface QuestionModalProps {
  questions: QuestionItem[];
  onSubmit: (answers: Record<string, QuestionAnswer>) => void;
  onJustFill: () => void;
  isSubmitting?: boolean;
  initialAnswers?: Record<string, QuestionAnswer>;
}

export function QuestionModal({
  questions,
  onSubmit,
  onJustFill,
  isSubmitting = false,
  initialAnswers,
}: QuestionModalProps) {
  const [answers, setAnswers] = useState<Record<string, QuestionAnswer>>(() => {
    const initial: Record<string, QuestionAnswer> = {};
    for (const q of questions) {
      initial[q.id] = initialAnswers?.[q.id] ?? { selectedOptionIds: [], freeText: '' };
    }
    return initial;
  });

  const handleOptionToggle = (questionId: string, optionId: string, questionType: string) => {
    setAnswers(prev => {
      const current = prev[questionId];
      if (questionType === 'single_choice' || questionType === 'confirm') {
        return { ...prev, [questionId]: { ...current, selectedOptionIds: [optionId] } };
      }
      const newIds = current.selectedOptionIds.includes(optionId)
        ? current.selectedOptionIds.filter(x => x !== optionId)
        : [...current.selectedOptionIds, optionId];
      return { ...prev, [questionId]: { ...current, selectedOptionIds: newIds } };
    });
  };

  const handleFreeTextChange = (questionId: string, text: string) => {
    setAnswers(prev => ({
      ...prev,
      [questionId]: { ...prev[questionId], freeText: text },
    }));
  };

  const handleSubmit = () => {
    const cleaned: Record<string, QuestionAnswer> = {};
    for (const q of questions) {
      const a = answers[q.id];
      if (q.question_type === 'free_text') {
        cleaned[q.id] = { selectedOptionIds: [], freeText: a.freeText?.trim() };
      } else if (q.question_type === 'confirm') {
        cleaned[q.id] = {
          selectedOptionIds: a.selectedOptionIds,
          freeText: a.freeText?.trim() || undefined,
        };
      } else {
        cleaned[q.id] = { selectedOptionIds: a.selectedOptionIds };
      }
    }
    onSubmit(cleaned);
  };

  const canSubmit = questions.every(q => {
    const a = answers[q.id];
    if (q.question_type === 'free_text') {
      return true;
    }
    return a.selectedOptionIds.length > 0;
  });

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 flex justify-center pb-6 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-xl mx-4 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden max-h-[70vh] flex flex-col">
        {/* Questions - scrollable */}
        <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
          {questions.map((q, idx) => (
            <SingleQuestionBlock
              key={q.id}
              question={q}
              index={idx}
              answer={answers[q.id]}
              onOptionToggle={(optId) => handleOptionToggle(q.id, optId, q.question_type)}
              onFreeTextChange={(text) => handleFreeTextChange(q.id, text)}
            />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-5 py-3 bg-gray-50 border-t border-gray-100 shrink-0">
          <button
            onClick={onJustFill}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          >
            Accept Draft
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className="px-5 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:bg-blue-300 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Processing...' : 'Submit All'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Single Question Block
// ============================================================================

interface SingleQuestionBlockProps {
  question: QuestionItem;
  index: number;
  answer: QuestionAnswer;
  onOptionToggle: (optionId: string) => void;
  onFreeTextChange: (text: string) => void;
}

function SingleQuestionBlock({
  question,
  index,
  answer,
  onOptionToggle,
  onFreeTextChange,
}: SingleQuestionBlockProps) {
  const resolvedOptions: QuestionOption[] =
    question.question_type === 'confirm' && (!question.options || question.options.length === 0)
      ? [
          { id: 'yes', label: 'はい' },
          { id: 'no', label: 'いいえ' },
        ]
      : (question.options ?? []);

  return (
    <div className="p-5">
      {/* Question text */}
      <p className="text-sm font-medium text-gray-900 leading-relaxed">
        <span className="text-xs text-gray-400 mr-2">Q{index + 1}.</span>
        {question.question}
      </p>

      {/* Options for single_choice / confirm */}
      {(question.question_type === 'single_choice' || question.question_type === 'confirm') &&
        resolvedOptions.length > 0 && (
          <div className="mt-3 space-y-2">
            {resolvedOptions.map(opt => (
              <label
                key={opt.id}
                className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                  answer.selectedOptionIds.includes(opt.id)
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
              >
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  checked={answer.selectedOptionIds.includes(opt.id)}
                  onChange={() => onOptionToggle(opt.id)}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">{opt.label}</span>
              </label>
            ))}
          </div>
        )}

      {/* Free text for corrections on confirm questions */}
      {question.question_type === 'confirm' && answer.selectedOptionIds.includes('no') && (
        <div className="mt-3">
          <textarea
            value={answer.freeText ?? ''}
            onChange={e => onFreeTextChange(e.target.value)}
            placeholder="修正内容を入力してください..."
            rows={2}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>
      )}

      {/* Options for multiple_choice */}
      {question.question_type === 'multiple_choice' && resolvedOptions.length > 0 && (
        <div className="mt-3 space-y-2">
          {resolvedOptions.map(opt => (
            <label
              key={opt.id}
              className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                answer.selectedOptionIds.includes(opt.id)
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <input
                type="checkbox"
                checked={answer.selectedOptionIds.includes(opt.id)}
                onChange={() => onOptionToggle(opt.id)}
                className="text-blue-600 focus:ring-blue-500 rounded"
              />
              <span className="text-sm text-gray-700">{opt.label}</span>
            </label>
          ))}
        </div>
      )}

      {/* Free text input */}
      {question.question_type === 'free_text' && (
        <div className="mt-3">
          <textarea
            value={answer.freeText ?? ''}
            onChange={e => onFreeTextChange(e.target.value)}
            placeholder="Type your answer..."
            rows={2}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>
      )}

      {/* Context */}
      {question.context && (
        <p className="mt-2 text-xs text-gray-400 leading-relaxed">{question.context}</p>
      )}
    </div>
  );
}
