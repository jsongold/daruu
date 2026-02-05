/**
 * Modal for entering free-form text as a data source.
 */

import { useState, useCallback, useRef, useEffect } from 'react';

interface TextInputModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string, content: string) => void;
  isSubmitting?: boolean;
}

export function TextInputModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting = false,
}: TextInputModalProps) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea when modal opens
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isOpen]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setName('');
      setContent('');
    }
  }, [isOpen]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (content.trim()) {
        const finalName = name.trim() || 'Text Input';
        onSubmit(finalName, content.trim());
      }
    },
    [name, content, onSubmit]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Submit on Cmd/Ctrl + Enter
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        if (content.trim()) {
          const finalName = name.trim() || 'Text Input';
          onSubmit(finalName, content.trim());
        }
      }
      // Close on Escape
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [content, name, onSubmit, onClose]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Add Text Data</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name field (optional) */}
          <div>
            <label htmlFor="text-name" className="block text-sm font-medium text-gray-700 mb-1">
              Name (optional)
            </label>
            <input
              id="text-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Personal Info"
              className="
                w-full px-3 py-2 border border-gray-300 rounded-lg
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                text-sm
              "
              disabled={isSubmitting}
            />
          </div>

          {/* Content field */}
          <div>
            <label htmlFor="text-content" className="block text-sm font-medium text-gray-700 mb-1">
              Content
            </label>
            <textarea
              id="text-content"
              ref={textareaRef}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter any information you want the AI to use for filling the form...

Example:
Name: John Smith
Date of Birth: January 15, 1985
Address: 123 Main St, City, State 12345
Email: john.smith@email.com"
              className="
                w-full px-3 py-2 border border-gray-300 rounded-lg
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                text-sm resize-none
              "
              rows={8}
              disabled={isSubmitting}
            />
            <p className="mt-1 text-xs text-gray-500">
              Tip: Use &quot;Field: Value&quot; format for best results.
              Press Cmd/Ctrl + Enter to submit.
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="
                px-4 py-2 text-sm font-medium text-gray-700
                hover:bg-gray-100 rounded-lg transition-colors
              "
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!content.trim() || isSubmitting}
              className="
                px-4 py-2 text-sm font-medium text-white bg-blue-600
                hover:bg-blue-700 rounded-lg transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                flex items-center gap-2
              "
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Adding...
                </>
              ) : (
                'Add Text'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
